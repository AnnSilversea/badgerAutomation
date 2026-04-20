"""Drake Automation Service - FastAPI app."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from drake_service.api.drake_routes import router as drake_router
from drake_service.api.workitems_routes import router as workitems_router
from drake_service.api.ocr_results_routes import router as ocr_results_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Drake Automation Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(drake_router)
app.include_router(workitems_router)
app.include_router(ocr_results_router)
