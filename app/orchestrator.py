"""Orquestador de producción (Railway).

Ejecuta las fases del pipeline en orden, cada una activable por
variable de entorno (por defecto: solo enriquecimiento, clasificación
y export, porque la cosecha de Google ya se corrió):

    RUN_SEARCH=true    -> fase 1: Google Places/Maps -> Supabase
    RUN_SCRAPE=true    -> fase 2: scraping de websites (default: true)
    RUN_CLASSIFY=true  -> fase 3: clasificación IA (default: true)
    RUN_SYNC=true      -> fase 4: export a Google Sheets (default: true)

Uso local:    python -m app.orchestrator
En Railway:   es el startCommand del contenedor.
"""

import asyncio
import os
import time

from app.services.business_pipeline import run_pipeline, FileCheckpoint
from app.services.classify_pipeline import run_classify_pipeline
from app.services.scrape_pipeline import run_scrape_pipeline
from app.sheets.sync import sync_to_sheets
from app.utils.helpers import ensure_google_credentials
from app.utils.logger import logger, log_task, _format_elapsed


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


def main() -> None:
    start = time.perf_counter()
    ensure_google_credentials()

    logger.success("=" * 60)
    logger.success("ORQUESTADOR INICIADO")
    logger.success(
        f"Fases: search={_flag('RUN_SEARCH', 'false')} "
        f"scrape={_flag('RUN_SCRAPE', 'true')} "
        f"classify={_flag('RUN_CLASSIFY', 'true')} "
        f"sync={_flag('RUN_SYNC', 'true')}"
    )
    logger.success("=" * 60)

    if _flag("RUN_SEARCH", "false"):
        with log_task("FASE 1: Búsqueda Google -> Supabase"):
            run_pipeline(checkpoint=FileCheckpoint())

    if _flag("RUN_SCRAPE", "true"):
        with log_task("FASE 2: Scraping de websites"):
            asyncio.run(run_scrape_pipeline())

    if _flag("RUN_CLASSIFY", "true"):
        with log_task("FASE 3: Clasificación IA"):
            run_classify_pipeline()

    if _flag("RUN_SYNC", "true"):
        with log_task("FASE 4: Export a Google Sheets"):
            exported = sync_to_sheets()
            logger.success(f"Exportados {exported} negocios")

    logger.success(
        f"ORQUESTADOR COMPLETADO en "
        f"{_format_elapsed(time.perf_counter() - start)}"
    )


if __name__ == "__main__":
    main()
