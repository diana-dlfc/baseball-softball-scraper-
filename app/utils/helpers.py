"""Utilidades generales del proyecto."""

import os
from pathlib import Path

from app.utils.logger import logger


def ensure_google_credentials() -> None:
    """Reconstruye credentials.json desde la variable de entorno.

    En Railway el JSON de la cuenta de servicio no puede ir en el repo;
    se guarda completo en GOOGLE_SHEETS_CREDENTIALS_JSON y este helper
    lo escribe a disco al arrancar el contenedor. En local, donde el
    archivo ya existe, no hace nada.
    """
    raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    path = Path(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/credentials.json")
    )
    if raw and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw, encoding="utf-8")
        logger.info(f"credentials.json reconstruido desde env var en {path}")
