import logging
import re
import shutil
from pathlib import Path
from typing import Tuple

from .utils import extract_pages_by_bookmark

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).parent
INPUT_DIR = MODULE_DIR / "input"
OUTPUT_DIR = MODULE_DIR / "output"


def ensure_storage_dirs() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "").name
    if not name:
        name = "file.pdf"
    name = re.sub(r"[^\w.\-]+", "_", name)
    return name


def build_paths(original_filename: str) -> Tuple[Path, Path, str]:
    safe_name = sanitize_filename(original_filename)
    base_name = Path(safe_name).stem or "file"
    output_filename = f"{base_name}_ExtractFilingInstructions.pdf"
    input_path = INPUT_DIR / safe_name
    output_path = OUTPUT_DIR / output_filename
    return input_path, output_path, output_filename


def save_upload_file(upload_file, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as f:
        shutil.copyfileobj(upload_file.file, f)


def extract_filing_instructions(
    input_path: Path,
    output_path: Path,
    search_text: str,
    max_items: int,
) -> int:
    ensure_storage_dirs()
    logger.info("Extracting filing instructions from '%s'.", input_path)
    return extract_pages_by_bookmark(
        str(input_path),
        str(output_path),
        search_text=search_text,
        max_items=max_items,
    )

