"""
Utility functions for PDF processing
"""
import logging
import os
from typing import Dict, List
import fitz  # PyMuPDF


def split_pdf_by_page_groups(
    input_pdf: str,
    page_groups: Dict[str, List[int]],
    output_dir: str
) -> Dict[str, str]:
    """
    Split a PDF into multiple PDFs based on page groups (0-based indexing)
    
    :param input_pdf: Path to input PDF file
    :param page_groups: Dictionary mapping group names to page indices
                        e.g., {"pages_7_8": [7,8], "pages_11_12": [11,12]}
    :param output_dir: Output directory for split PDFs
    :return: Dictionary mapping group names to output PDF paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(input_pdf)
    total_pages = len(doc)
    
    # Flatten form fields to ensure values are preserved in split pages
    try:
        for page in doc:
            if hasattr(page, "flatten_annots"):
                page.flatten_annots()
    except Exception as e:
        print(f"Warning: Could not flatten annotations: {e}")
    
    # Reload document from memory to ensure flattening is baked in
    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    doc = fitz.open("pdf", pdf_bytes)
    
    base_name = os.path.splitext(os.path.basename(input_pdf))[0]
    output_paths = {}
    
    for suffix, pages in page_groups.items():
        # Use select() on a fresh copy to preserve form data/flattening better than insert_pdf
        with fitz.open("pdf", pdf_bytes) as new_doc:
            valid_pages = [p for p in pages if 0 <= p < total_pages]
            
            if valid_pages:
                new_doc.select(valid_pages)
                
                output_pdf = os.path.join(
                    output_dir,
                    f"{base_name}_{suffix}.pdf"
                )
                
                new_doc.save(output_pdf)
                output_paths[suffix] = output_pdf
            else:
                print(f"⚠️ No valid pages found for group {suffix} (requested: {pages})")
    
    doc.close()
    return output_paths


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get the total number of pages in a PDF
    
    :param pdf_path: Path to PDF file
    :return: Number of pages
    """
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count
