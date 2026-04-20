from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os, json, time

from di_client import extract_pages_text_smart
from llm_client import find_page_map_with_llm, llm_extract_single_prompt

load_dotenv()

app = FastAPI(title="PDF -> JSON (Smart PyPDF + DI + AzureOpenAI)")


def log_step(step: str, start: float):
    elapsed = time.perf_counter() - start
    print(f"[TIME] {step}: {elapsed:.3f}s")


def _build_relevant_pages(page_map: dict) -> list[int]:
    """
    Collect relevant pages from page_map.
    Supports:
      - single page keys: int or None
      - form_1040_page: int | list[int] | None
      - attachment keys: list[int]
    """
    single_or_list_keys = ("page1", "schedule_l", "schedule_m1", "schedule_m2", "form_1040_page")
    attachment_keys = (
        "w2_pages",
        "1099_int_pages", "1099_div_pages", "1099_nec_pages",
        "1099_ssa_pages", "1099_r_pages",
    )

    relevant = []

    # keys that can be int or list
    for k in single_or_list_keys:
        v = page_map.get(k)
        if v is None:
            continue
        if isinstance(v, list):
            relevant.extend(v)
        else:
            relevant.append(v)

    # attachments are lists
    for k in attachment_keys:
        relevant.extend(page_map.get(k) or [])

    # normalize -> unique sorted ints
    out = []
    for x in relevant:
        if x is None:
            continue
        try:
            out.append(int(x))
        except Exception:
            pass

    return sorted(set(out))


@app.post("/pdf-to-json")
async def pdf_to_json(
    file: UploadFile = File(...),
    di_model_id: str = Query(default="prebuilt-layout")
):
    req_id = int(time.time() * 1000)
    t0 = time.perf_counter()
    print(f"[REQ {req_id}] [START] Processing file: {file.filename}")

    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(status_code=400, content={"error": "Please upload a PDF file."})

    # ─────────────────────────────
    # Read PDF
    # ─────────────────────────────
    t_read = time.perf_counter()
    pdf_bytes = await file.read()
    log_step(f"[REQ {req_id}] Read PDF bytes", t_read)

    if not pdf_bytes:
        return JSONResponse(status_code=400, content={"error": "Empty PDF upload (0 bytes)."})

    # ─────────────────────────────
    # Save PDF (avoid overwrite/lock by timestamp)
    # ─────────────────────────────
    t_save_pdf = time.perf_counter()
    pdf_dir = "pdfs"
    exports_dir = "exports"
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(exports_dir, exist_ok=True)

    base = file.filename.rsplit(".", 1)[0]
    ts = time.strftime("%Y%m%d_%H%M%S")
    pdf_path = os.path.join(pdf_dir, f"{base}_{ts}_{req_id}.pdf")

    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    log_step(f"[REQ {req_id}] Save PDF to disk", t_save_pdf)

    # ─────────────────────────────
    # SMART text extraction (PyPDF + DI)
    # ─────────────────────────────
    t_extract = time.perf_counter()
    pages = extract_pages_text_smart(pdf_bytes, di_model_id=di_model_id)
    log_step(f"[REQ {req_id}] Extract pages text (PyPDF + DI)", t_extract)

    print(f"[REQ {req_id}] [INFO] Total pages extracted: {len(pages)}")
    print(f"[REQ {req_id}] [INFO] Pages source breakdown: "
          f"PyPDF={sum(1 for p in pages if p.get('source')=='pypdf')}, "
          f"DI={sum(1 for p in pages if p.get('source')=='di')}")

    # ─────────────────────────────
    # Page map detection (LLM-assisted)
    # ─────────────────────────────
    t_page_map = time.perf_counter()
    page_map = find_page_map_with_llm(pages)
    log_step(f"[REQ {req_id}] Find page_map (LLM)", t_page_map)

    print(f"[REQ {req_id}] [INFO] page_map = {page_map}")

    # ─────────────────────────────
    # Filter relevant pages only (FIX: supports list pages for 1040 + attachments)
    # ─────────────────────────────
    t_filter = time.perf_counter()
    relevant_pages = _build_relevant_pages(page_map)
    print(f"[REQ {req_id}] [DEBUG] relevant_pages = {relevant_pages}")

    filtered_pages = [p for p in pages if int(p.get("page_number")) in relevant_pages]

    filtered_text = "\n---PAGE BREAK---\n".join(
        f"[PAGE {p['page_number']}]\n{p.get('text','')}" for p in filtered_pages
    ).strip()

    log_step(f"[REQ {req_id}] Filter relevant pages + build text", t_filter)

    if not filtered_text:
        log_step(f"[REQ {req_id}] TOTAL (early exit)", t0)
        return JSONResponse(status_code=200, content={
            "document_type": "",
            "fields": {},
            "tables": [],
            "page_map": page_map,
            "pdf_saved_to": pdf_path
        })

    # ─────────────────────────────
    # LLM extraction
    # ─────────────────────────────
    t_llm = time.perf_counter()
    try:
        structured = llm_extract_single_prompt(filtered_text)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "LLM failed to produce valid JSON",
                "detail": str(e),
                "page_map": page_map,
                "relevant_pages": relevant_pages,
                "pdf_saved_to": pdf_path,
            }
        )
    log_step(f"[REQ {req_id}] LLM extract structured JSON", t_llm)

    # ─────────────────────────────
    # Finalize & save
    # ─────────────────────────────
    t_save_out = time.perf_counter()
    structured["page_map"] = page_map

    out_json_path = os.path.join(exports_dir, f"{base}_{ts}_{req_id}_extracted.json")
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(structured, f, indent=2, ensure_ascii=False)

    structured["pdf_saved_to"] = pdf_path
    structured["json_saved_to"] = out_json_path
    log_step(f"[REQ {req_id}] Save final JSON", t_save_out)

    # ─────────────────────────────
    # TOTAL TIME
    # ─────────────────────────────
    log_step(f"[REQ {req_id}] TOTAL PROCESSING TIME", t0)

    return structured
