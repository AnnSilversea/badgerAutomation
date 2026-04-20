"""
Drake Automation Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Drake Application
DRAKE_EXE = os.getenv("DRAKE_EXE", "")
DRAKE_CWD = os.getenv("DRAKE_CWD", "")
DRAKE_TITLE = "Drake 2025 Tax Software"

DRAKE24_EXE = os.getenv("DRAKE24_EXE", r"D:\DRAKE24\FT\DSTART2024.EXE")
DRAKE24_CWD = os.getenv("DRAKE24_CWD", r"D:\DRAKE24\FT")
DRAKE24_TITLE = "Drake 2024 Tax Software"

# Credentials
USERNAME = os.getenv("USERNAME_DRAKE", "")
PASSWORD = os.getenv("PASSWORD_DRAKE", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")

# Timeouts
TIMEOUT_DEFAULT = 60
TIMEOUT_WINDOW = 30
TIMEOUT_CONTROL = 5

# Retry
MAX_RETRIES = 3
RETRY_DELAY = 0.5

# Validation
VALIDATE_CREDENTIALS = all([USERNAME, PASSWORD, CLIENT_ID])

# Export
EXPORT_FOLDER = os.getenv("EXPORT_FOLDER", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "exports")))
os.makedirs(EXPORT_FOLDER, exist_ok=True)

# Export
FOLDER_PRINTER = os.getenv("FOLDER_PRINTER", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "printers")))
os.makedirs(FOLDER_PRINTER, exist_ok=True)
