def build_page_text_map(di_result: dict) -> dict[int, str]:
    page_map = {}
    for page in di_result.get("pages", []):
        pno = page.get("pageNumber")  # bắt đầu từ 1
        lines = [l.get("content","") for l in page.get("lines", []) if l.get("content")]
        page_map[pno] = "\n".join(lines)
    return page_map

def find_pages(page_map: dict[int, str], keywords: list[str]) -> dict[str, list[int]]:
    out = {}
    for kw in keywords:
        hits = [p for p,t in page_map.items() if kw.lower() in (t or "").lower()]
        out[kw] = hits
    return out

def collect_pages_text(page_map: dict[int, str], pages: list[int]) -> str:
    chunks = []
    for p in sorted(set(pages)):
        chunks.append(f"\n\n=== PAGE {p} ===\n{page_map.get(p,'')}")
    return "".join(chunks)
