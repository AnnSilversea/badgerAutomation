"""
Azure Document Intelligence client
"""
import os
import logging
import time
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentField
from azure.core.credentials import AzureKeyCredential

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Azure client
_endpoint = os.environ.get("AZURE_DI_ENDPOINT")
_key = os.environ.get("AZURE_DI_KEY")

if not _endpoint or not _key:
    raise ValueError("AZURE_DI_ENDPOINT and AZURE_DI_KEY must be set in environment variables")

_client = DocumentIntelligenceClient(
    endpoint=_endpoint,
    credential=AzureKeyCredential(_key)
)


def parse_field(field: DocumentField) -> Any:
    """
    Recursively parse Azure DocumentField to extract values.
    Handles all field types: string, number, date, boolean, array, and object.
    
    :param field: Azure DocumentField object
    :return: Extracted value (string, number, date string, boolean, list, or dict)
    """
    if field is None:
        return None

    if field.value_string is not None:
        return field.value_string

    if field.value_number is not None:
        return field.value_number

    if field.value_date is not None:
        return field.value_date.isoformat()

    if field.value_boolean is not None:
        return field.value_boolean

    if field.value_array is not None:
        return [parse_field(item) for item in field.value_array]

    if field.value_object is not None:
        return {
            k: parse_field(v)
            for k, v in field.value_object.items()
        }
    
    # Fallback to content if available
    return field.content if hasattr(field, 'content') else None


def analyze_pdf_with_model(model_id: str, pdf_path: str, pages: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze a PDF subset using a custom Azure Document Intelligence model
    
    :param model_id: Azure Document Intelligence model ID
    :param pdf_path: Path to PDF file
    :param pages: Optional page range to analyze (e.g. "1-3", "1,5")
    :return: Dictionary containing extracted fields and metadata
    """
    # Read PDF file
    read_start = time.time()
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    file_size_mb = len(pdf_bytes) / (1024 * 1024)
    logger.debug(f"   📖 Read PDF ({file_size_mb:.2f} MB) in {time.time() - read_start:.2f}s")
    
    # Start Azure analysis
    api_start = time.time()
    logger.debug(f"   🌐 Sending request to Azure Document Intelligence API...")
    
    try:
        poller = _client.begin_analyze_document(
            model_id=model_id,
            body=AnalyzeDocumentRequest(bytes_source=pdf_bytes),
            pages=pages
        )
        
        upload_time = time.time() - api_start
        logger.debug(f"   📤 Request sent (Upload) in {upload_time:.2f}s. Waiting for completion...")

        # Wait for result (this is the slow part)
        wait_start = time.time()
        result = poller.result()
        
        process_time = time.time() - wait_start
        logger.debug(f"   ✅ Azure API processing completed in {process_time:.2f}s")
        
    except Exception as e:
        api_time = time.time() - api_start
        logger.error(f"   ❌ Azure API call failed after {api_time:.2f}s: {str(e)}")
        raise
    
    if not result.documents:
        logger.warning(f"   ⚠️  No documents found in result")
        return {
            "_model_id": model_id,
            "_pdf_path": pdf_path,
            "_confidence": None,
            "fields": {}
        }
    
    # Process results
    process_start = time.time()
    doc = result.documents[0]
    fields_out: Dict[str, Any] = {}
    
    # Use recursive parsing for all field types (handles string, number, date, boolean, array, object)
    for field_name, field in doc.fields.items():
        fields_out[field_name] = parse_field(field)
    
    process_time = time.time() - process_start
    logger.debug(f"   🔄 Processed {len(fields_out)} fields in {process_time:.2f}s")
    
    return {
        "_model_id": model_id,
        "_pdf_path": pdf_path,
        "_confidence": doc.confidence,
        "fields": fields_out
    }
