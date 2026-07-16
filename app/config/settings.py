"""Configuración general del scraper."""

import os

from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# Motor de búsqueda: "auto" (Places con fallback a Maps), "places" o "maps"
SEARCH_ENGINE = os.getenv("SEARCH_ENGINE", "auto").lower()

# --- LLM (clasificador IA) ---
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/deepseek-v4-flash")

LLM_FALLBACK_API_KEY = os.getenv("LLM_FALLBACK_API_KEY")
LLM_FALLBACK_BASE_URL = os.getenv("LLM_FALLBACK_BASE_URL")
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL")

LLM_FALLBACK2_API_KEY = os.getenv("LLM_FALLBACK2_API_KEY")
LLM_FALLBACK2_BASE_URL = os.getenv("LLM_FALLBACK2_BASE_URL")
LLM_FALLBACK2_MODEL = os.getenv("LLM_FALLBACK2_MODEL")

LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 1500  # margen para modelos que razonan pese a thinking=false
LLM_DISABLE_THINKING = True  # apaga el razonamiento (innecesario y lento)
CLASSIFY_WORKERS = 2         # 2 workers x 2 proveedores en rotación

# --- Google Sheets ---
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/credentials.json"
)

GOOGLE_PLACES_PAGE_SIZE = 20
REQUEST_DELAY = 2       # pausa entre páginas de una misma búsqueda
SEARCH_DELAY = 2        # pausa entre búsquedas del pipeline
MAX_RETRIES = 3
PLAYWRIGHT_TIMEOUT = 30000
EXPORT_BATCH_SIZE = 500
HEADLESS = True
MAX_CONCURRENT_PAGES = 3
GOOGLE_TIMEOUT = 30
