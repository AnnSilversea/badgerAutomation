"""Drake Service configuration - loads from .env at project root."""
import os
from pathlib import Path

# Load .env from project root (parent of drake_service)
_root = Path(__file__).resolve().parent.parent.parent
_env_path = _root / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SERVICE_B_PORT = int(os.getenv("SERVICE_B_PORT", "8001"))
