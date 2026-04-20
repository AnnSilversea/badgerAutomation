import logging
import os
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

def extract_pages_by_bookmark(input_path, output_path, search_text="FI", max_items=5):
    """
    Find bookmarks containing a keyword and extract the corresponding pages.

    Args:
        input_path (str): Path to the input PDF file.
        output_path (str): Path for the output PDF file.
        search_text (str): Bookmark text to match (e.g., "FI").
        max_items (int): Maximum number of pages to extract.
    """
    
    if not os.path.exists(input_path):
        logger.error("Input file not found: '%s'.", input_path)
        return 0

    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    found_count = 0
    found_pages = set() # Use a set to avoid duplicates when multiple bookmarks point to a page
    found_page_list = [] # Preserve discovery order for writing output
    search_text_lower = search_text.lower()

    logger.info(
        "Reading bookmarks from '%s' to find entries containing '%s'...",
        input_path,
        search_text,
    )

    def _search_outline(outline_items):
        nonlocal found_count
        for item in outline_items:
            # Stop immediately if we already reached the requested count
            if found_count >= max_items:
                return True

            # If item is a list (child bookmarks), recurse into it
            if isinstance(item, list):
                if _search_outline(item):
                    return True
                continue
            
            # Check bookmark title
            title = getattr(item, "title", "") or ""
            if search_text_lower in title.lower():
                try:
                    # Resolve page number from bookmark destination
                    page_number = reader.get_destination_page_number(item)
                    
                    # Add page only if not already captured (avoid duplicates)
                    if page_number not in found_pages:
                        found_pages.add(page_number)
                        found_page_list.append(page_number)
                        found_count += 1
                        logger.info(
                            "Found bookmark '%s' pointing to page %s.",
                            title,
                            page_number + 1,
                        )
                except Exception as e:
                    logger.exception(
                        "Failed to read page for bookmark '%s': %s",
                        title,
                        e,
                    )
        return False

    # Start searching from the root outline list
    outline = getattr(reader, "outlines", None)
    if outline is None:
        outline = getattr(reader, "outline", None)

    if outline:
        _search_outline(outline)
    else:
        logger.warning("This PDF has no bookmarks (outline).")
        return 0

    if found_count > 0:
        for page_number in found_page_list:
            page = reader.pages[page_number]
            writer.add_page(page)
        with open(output_path, "wb") as f:
            writer.write(f)
        logger.info("Success! Extracted %s page(s).", found_count)
        logger.info("Output file saved to: %s", output_path)
    else:
        logger.info(
            "No bookmarks found with titles containing '%s'.",
            search_text,
        )
    return found_count