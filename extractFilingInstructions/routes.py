import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .service import build_paths, extract_filing_instructions, OUTPUT_DIR, save_upload_file

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/extract")
async def extract_filing_instructions_endpoint(
    file: UploadFile = File(...),
    search_text: str = Form("FI"),
    max_items: int = Form(5),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    if max_items <= 0:
        raise HTTPException(status_code=400, detail="max_items must be greater than 0.")

    input_path, output_path, output_filename = build_paths(file.filename)
    save_upload_file(file, input_path)

    extracted_count = extract_filing_instructions(
        input_path=input_path,
        output_path=output_path,
        search_text=search_text,
        max_items=max_items,
    )
    if extracted_count <= 0 or not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No matching bookmarks found for '{search_text}'.",
        )

    download_url = f"/api/filing-instructions/download/{output_filename}"
    return JSONResponse(
        {
            "output_name": output_filename,
            "download_url": download_url,
            "extracted_count": extracted_count,
        }
    )


@router.get("/download/{filename}")
def download_filing_instructions(filename: str):
    safe_name = Path(filename).name
    file_path = OUTPUT_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=safe_name,
    )

