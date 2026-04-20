import os
import io
from typing import List, Dict, Any

import fitz  # PyMuPDF

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential


# =========================
# 1) Azure DI (full file)
# =========================
def analyze_pdf_bytes(pdf_bytes: bytes, model_id: str = "prebuilt-layout") -> dict:
    client = DocumentIntelligenceClient(
        endpoint=os.environ["AZURE_DI_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["AZURE_DI_KEY"]),
    )

    poller = client.begin_analyze_document(
        model_id=model_id,
        body=AnalyzeDocumentRequest(bytes_source=pdf_bytes),
    )
    result = poller.result()
    return result.as_dict()


def extract_pages_text_from_di(di_result: dict) -> List[Dict[str, Any]]:
    """
    Convert DI result to page texts. IMPORTANT:
    - pageNumber returned by DI is 1-based and matches the PDF order for the analyzed PDF bytes.
    - If you analyzed a subset PDF, DI's pageNumber is relative to that subset (not the original).
    """
    pages: List[Dict[str, Any]] = []
    for p in di_result.get("pages", []):
        page_number = p.get("pageNumber")  # 1-based inside analyzed file
        text = " ".join(
            line.get("content", "")
            for line in p.get("lines", [])
            if line.get("content")
        ).strip()

        pages.append({
            "page_number": page_number,
            "text": text,
            "source": "di"
        })
    return pages


# =========================
# 2) PyMuPDF (fast text)
# =========================
def extract_pages_text_pymupdf_from_bytes(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: List[Dict[str, Any]] = []

    for i in range(doc.page_count):
        page = doc[i]
        raw = page.get_text() or ""
        text = " ".join(raw.split()).strip()
        pages.append({
            "page_number": i + 1,     # 1-based PDF page index (TRUE index)
            "text": text,
            "source": "pymupdf"
        })
    doc.close()
    return pages


# =========================
# 3) Heuristics: decide DI
# =========================
def _score_text_quality(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Simple deterministic metrics to decide if PyPDF text is good enough.
    """
    total_chars = sum(len(p["text"]) for p in pages)
    empty_pages = sum(1 for p in pages if len(p["text"]) < 30)
    page_count = max(1, len(pages))
    empty_ratio = empty_pages / page_count

    # keyword presence for tax forms (helps detect "text exists but useless")
    joined = " ".join(p["text"] for p in pages).lower()
    has_tax_signals = any(k in joined for k in [
        "form 1120-s", "schedule l", "schedule m-1", "schedule m-2",
        "balance sheets per books", "u.s. income tax return"
    ])

    return {
        "total_chars": total_chars,
        "empty_pages": empty_pages,
        "page_count": page_count,
        "empty_ratio": empty_ratio,
        "has_tax_signals": has_tax_signals
    }


def should_use_di_full(pages_pypdf: List[Dict[str, Any]]) -> bool:
    """
    Decide whether to send the WHOLE PDF to DI (more accurate but more cost).
    - If PyPDF text is almost empty, DI full is best.
    - If this is clearly a tax return but PyPDF missed key headers, DI full is safer.
    """
    m = _score_text_quality(pages_pypdf)

    if m["total_chars"] < 1200:
        return True

    if m["empty_ratio"] >= 0.60:
        return True

   
    if (not m["has_tax_signals"]) and m["total_chars"] < 6000:
        return True

    return False


def pages_need_di_subset(pages_pypdf: List[Dict[str, Any]], empty_page_chars: int = 30) -> List[int]:
    """
    Identify specific pages (1-based) that likely need DI.
    Basic rule: pages with very low extracted text.
    """
    return [p["page_number"] for p in pages_pypdf if len(p["text"]) < empty_page_chars]


# =========================
# 4) Split PDF subset bytes
# =========================
def build_subset_pdf_bytes(pdf_bytes: bytes, page_numbers_1_based: List[int]) -> bytes:
    """
    Create a new PDF bytes containing only selected pages (keeps original order).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    subset_doc = fitz.open()  # Create empty PDF

    max_page = doc.page_count
    valid_pages = [n for n in page_numbers_1_based if 1 <= n <= max_page]
    for n in valid_pages:
        subset_doc.insert_pdf(doc, from_page=n-1, to_page=n-1)

    # Use tobytes() to get PDF bytes directly (more reliable than BytesIO)
    subset_bytes = subset_doc.write()
    
    doc.close()
    subset_doc.close()
    return subset_bytes


# =========================
# 5) MAIN: Smart extraction
# =========================
def extract_pages_text_smart(
    pdf_bytes: bytes,
    di_model_id: str = "prebuilt-layout",
    *,
    empty_page_chars: int = 30,     # trang nào < 30 chars coi là trống
    min_di_text_chars: int = 10,    # nếu DI trả < 10 chars thì vẫn giữ PyPDF
) -> List[Dict[str, Any]]:
    """
    Expert mode (EMPTY-PAGES-ONLY):
    1) Always extract text by PyPDF for all pages (cheap/fast).
    2) Identify pages whose PyPDF text is too empty.
    3) Send ONLY those pages to Azure DI (subset PDF).
    4) Merge DI text back into original page list.
    NOTE: No "DI full" in this mode.
    """

    # Step A: PyPDF first (all pages)
    pages_pypdf = extract_pages_text_pymupdf_from_bytes(pdf_bytes)

    # Step B: find weak/empty pages
    weak_pages = [p["page_number"] for p in pages_pypdf if len(p["text"]) < empty_page_chars]

    print(f"[DI] EMPTY-PAGES-ONLY mode. weak_pages={len(weak_pages)}")

    # If no weak pages, return PyPDF pages
    if not weak_pages:
        return pages_pypdf

    # Step C: DI only weak pages (subset pdf)
    subset_bytes = build_subset_pdf_bytes(pdf_bytes, weak_pages)
    di_subset_result = analyze_pdf_bytes(subset_bytes, model_id=di_model_id)
    subset_pages_di = extract_pages_text_from_di(di_subset_result)

    # DI subset pages are 1..len(weak_pages) in order; map back to original page numbers
    subset_pages_di_sorted = sorted(subset_pages_di, key=lambda x: x["page_number"])
    mapped_di_by_original: Dict[int, str] = {}
    for idx, di_page in enumerate(subset_pages_di_sorted):
        if idx < len(weak_pages):
            original_page_no = weak_pages[idx]
            mapped_di_by_original[original_page_no] = (di_page["text"] or "").strip()

    # Step D: merge back: replace only if DI text is meaningful
    merged: List[Dict[str, Any]] = []
    for p in pages_pypdf:
        n = p["page_number"]
        di_text = mapped_di_by_original.get(n)

        if di_text and len(di_text) >= min_di_text_chars:
            merged.append({
                "page_number": n,
                "text": di_text,
                "source": "di"
            })
        else:
            merged.append(p)

    return merged


# =========================
# 6) Debug Utilities
# =========================
def debug_split_pages_to_output(pdf_path: str, output_dir: str, page_numbers: List[int] = None) -> List[Dict[str, Any]]:
    """
    Split a PDF into single-page images (PNG) and save them to the output directory.
    Useful for debugging page extraction/splitting issues.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    
    # Flatten form fields to ensure values are preserved in split pages/images
    try:
        for page in doc:
            if hasattr(page, "flatten_annots"):
                page.flatten_annots()
    except Exception as e:
        print(f"Warning: Could not flatten annotations: {e}")

    # Reload document from memory to ensure flattening is baked in before splitting
    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    doc = fitz.open("pdf", pdf_bytes)

    saved_pages = []
    
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]

    if page_numbers is not None:
        target_indices = sorted(list(set(p for p in page_numbers if 0 <= p < len(doc))))
    else:
        target_indices = range(len(doc))

    for i in target_indices:
        page = doc[i]
        # Render page to image (zoom=2 for better quality)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        out_name = f"{base_name}_page_{i+1}.png"
        out_path = os.path.join(output_dir, out_name)
        pix.save(out_path)

        # Also save a single-page PDF for processing
        pdf_out_name = f"{base_name}_page_{i+1}.pdf"
        pdf_out_path = os.path.join(output_dir, pdf_out_name)
        
        with fitz.open("pdf", pdf_bytes) as single_page_doc:
            single_page_doc.select([i])
            single_page_doc.save(pdf_out_path)
        
        # Extract text
        text = page.get_text()
        
        saved_pages.append({
            "filename": out_name,
            "pdf_path": pdf_out_path,
            "text": text,
            "page_number": i + 1
        })

    doc.close()
    return saved_pages
