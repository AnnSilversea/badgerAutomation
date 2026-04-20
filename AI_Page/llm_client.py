import os
import json
import re
from openai import AzureOpenAI

from .prompts import (
    SYSTEM_PROMPT_EXTRACTION,
    SYSTEM_PROMPT_PAGE_DETECTION,
    SCHEMA_PROMPT,
    PAGE_DETECTION_PROMPT,
    REPAIR_PROMPT,
)
def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # handle ```json ... ```
        parts = s.split("```")
        if len(parts) >= 3:
            inner = parts[1].strip()
            # remove optional leading "json"
            if inner.lower().startswith("json"):
                inner = inner[4:].strip()
            return inner
    return s


def _extract_first_json_object(s: str) -> str | None:
    """
    Try to extract the first top-level JSON object {...} from a string.
    Works even if model adds extra text before/after.
    """
    s = s.strip()
    start = s.find("{")
    if start == -1:
        return None

    depth = 0
    in_str = False
    escape = False

    for i in range(start, len(s)):
        ch = s[i]

        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue

        # not in string
        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]

    return None


def _truncate_text(text: str, max_chars: int = 45000) -> str:
    """
    Truncate input text to reduce token overflow risk.
    Use chars-based truncation (simple + reliable).
    """
    text = text or ""
    if len(text) <= max_chars:
        return text
    # keep head + tail (often headers on head, totals on tail)
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3):]
    return head + "\n\n[TRUNCATED]\n\n" + tail


def llm_text_to_json(text: str, schema_prompt: str, *, max_repair: int = 1) -> dict:
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    key = os.environ["AZURE_OPENAI_KEY"]
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=key,
        api_version=api_version,
    )

    text = _truncate_text(text, max_chars=45000)

    user_prompt = schema_prompt + "\n\nNội dung PDF:\n" + text

    def _call_llm(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=deployment,
            temperature=0.0,
            max_tokens=1600,  # tăng chút để đủ JSON + giảm chance bị cắt ngang
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION},
                {"role": "user", "content": prompt},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    # 1) main call
    content = _call_llm(user_prompt)
    content = _strip_code_fences(content)

    # 2) attempt parse from extracted JSON block
    candidate = _extract_first_json_object(content) or content
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        # 3) repair loop (usually 1 is enough)
        bad = candidate
        last_err = e

        for _ in range(max_repair):
            fixed = _call_llm(REPAIR_PROMPT + bad)
            fixed = _strip_code_fences(fixed)
            fixed_candidate = _extract_first_json_object(fixed) or fixed

            try:
                return json.loads(fixed_candidate)
            except json.JSONDecodeError as e2:
                bad = fixed_candidate
                last_err = e2

        # 4) raise with debug snippet
        snippet = bad[:800].replace("\n", "\\n")
        raise ValueError(
            f"LLM failed to produce valid JSON after repair. "
            f"Last error: {last_err}. Output snippet: {snippet}"
        )


# Build schema prompt with instructions for filtered text format
# (Now imported from prompts.py)


def llm_extract_single_prompt(text: str) -> dict:
    """
    Extract tax form data from filtered text using optimized prompt.
    Text should contain only [PAGE n] marked sections.
    """
    return llm_text_to_json(text, SCHEMA_PROMPT)


# ========== PAGE DETECTION WITH AZURE OpenAI ==========

# Prompts imported from prompts.py
PAGE_DETECTION_SYSTEM_PROMPT = SYSTEM_PROMPT_PAGE_DETECTION


def find_page_map_with_llm(pages: list) -> dict:
    """
    Use Azure OpenAI to intelligently identify tax form page numbers.
    Much more accurate than pattern matching for different form types.
    
    Args:
        pages: list of {"page_number": int, "text": str, "source": str}
    
    Returns:
        {"page1": int or None, "schedule_l": int or None, "schedule_m1": int or None, "schedule_m2": int or None}
    """
    try:
        # Build page summary (first 1000 chars per page for efficiency)
        pages_summary = ""
        for p in pages:
            page_num = p.get("page_number", "?")
            text_preview = (p.get("text") or "")[:1000]
            pages_summary += f"[PAGE {page_num}]\n{text_preview}\n\n"
        
        # Prepare prompt
        user_prompt = PAGE_DETECTION_PROMPT + pages_summary
        
        # Call LLM
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
        key = os.environ["AZURE_OPENAI_KEY"]
        deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
        
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=key,
            api_version=api_version,
        )
        
        resp = client.chat.completions.create(
            model=deployment,
            temperature=0.0,
            max_tokens=500,
            messages=[
                {"role": "system", "content": PAGE_DETECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        
        content = (resp.choices[0].message.content or "").strip()
        content = _strip_code_fences(content)
        
        # Extract JSON
        json_str = _extract_first_json_object(content) or content
        result = json.loads(json_str)
        
        # Validate and return
        # Build normalized page_map with new keys (ensure keys exist)
        page_map = {
            "clients": result.get("clients") or [],
            "page1": result.get("page1"),
            "schedule_l": result.get("schedule_l"),
            "schedule_m1": result.get("schedule_m1"),
            "schedule_m2": result.get("schedule_m2"),
            "form_1040_page": result.get("form_1040_page"),
            "w2_pages": result.get("w2_pages") or [],
            "1099_int_pages": result.get("1099_int_pages") or [],
            "1099_div_pages": result.get("1099_div_pages") or [],
            "1099_nec_pages": result.get("1099_nec_pages") or [],
            "1099_ssa_pages": result.get("1099_ssa_pages") or [],
            "1099_r_pages": result.get("1099_r_pages") or [],
        }

        return page_map
    
    except Exception as e:
        # Fallback to pattern matching if LLM fails
        print(f"⚠️  LLM page detection failed: {e}")
        print("⏮️  Falling back to pattern matching...")
        from page_locator import find_page_map as find_page_map_fallback
        return find_page_map_fallback(pages)
