"""Sistema de logs de producción basado en Loguru.

Uso en cualquier módulo del proyecto:

    from app.utils.logger import logger

    logger.info("mensaje")
    logger.success("operación exitosa")
    logger.exception("algo falló")   # dentro de un except: incluye stack trace

Helpers de pipeline:

    from app.utils.logger import log_task, log_search_end, ...

    with log_task("Scraping de websites"):
        ...
"""

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from loguru import logger

# ---------------------------------------------------------------------------
# Configuración de sinks
# ---------------------------------------------------------------------------

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Nivel de consola configurable desde el .env (LOG_LEVEL=DEBUG para depurar)
CONSOLE_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{module}:{function}:{line} | {message}"
)

logger.remove()

# 1) Consola con colores (Railway captura stdout/stderr automáticamente)
logger.add(
    sys.stderr,
    format=CONSOLE_FORMAT,
    level=CONSOLE_LEVEL,
    colorize=True,
    backtrace=True,
    diagnose=False,  # no volcar valores de variables (API keys) en consola
)

# 2) Log completo con rotación y retención.
#    enqueue=True hace el logging seguro entre hilos y procesos
#    (importante con Playwright y tareas concurrentes).
logger.add(
    LOGS_DIR / "scraper.log",
    format=FILE_FORMAT,
    level="DEBUG",
    rotation="10 MB",
    retention="14 days",
    compression="zip",
    enqueue=True,
    backtrace=True,
    diagnose=False,  # False: evita volcar valores de variables (API keys) al log
)

# 3) Solo errores, retención más larga para auditoría
logger.add(
    LOGS_DIR / "errors.log",
    format=FILE_FORMAT,
    level="ERROR",
    rotation="5 MB",
    retention="30 days",
    compression="zip",
    enqueue=True,
    backtrace=True,
    diagnose=False,
)


# ---------------------------------------------------------------------------
# Helpers del pipeline
# ---------------------------------------------------------------------------

def log_scraper_start() -> None:
    logger.success("=" * 60)
    logger.success("SCRAPER INICIADO")
    logger.success("=" * 60)


def log_scraper_end(total_businesses: int, elapsed_seconds: float) -> None:
    logger.success("=" * 60)
    logger.success(
        f"SCRAPER FINALIZADO | {total_businesses} negocios | "
        f"{_format_elapsed(elapsed_seconds)}"
    )
    logger.success("=" * 60)


def log_state_start(state: str) -> None:
    logger.info(f"[{state}] Iniciando estado")


def log_state_end(state: str, found: int, elapsed_seconds: float) -> None:
    logger.success(
        f"[{state}] Estado completado | {found} negocios | "
        f"{_format_elapsed(elapsed_seconds)}"
    )


def log_search_start(query: str, state: str) -> None:
    logger.info(f"[{state}] Buscando: '{query}'")


def log_search_end(query: str, state: str, found: int) -> None:
    logger.info(f"[{state}] '{query}' -> {found} resultados")


def log_db_summary(inserted: int, updated: int, skipped: int = 0) -> None:
    logger.info(
        f"Supabase: {inserted} insertados | {updated} actualizados | "
        f"{skipped} omitidos"
    )


@contextmanager
def log_task(name: str):
    """Mide y registra la duración de una tarea. Registra la excepción si falla.

        with log_task("Búsqueda en Florida"):
            ...
    """
    logger.info(f"Tarea iniciada: {name}")
    start = time.perf_counter()
    try:
        yield
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception(
            f"Tarea FALLIDA: {name} ({_format_elapsed(elapsed)})"
        )
        raise
    else:
        elapsed = time.perf_counter() - start
        logger.success(f"Tarea completada: {name} ({_format_elapsed(elapsed)})")


def _format_elapsed(seconds: float) -> str:
    """Convierte segundos a un formato legible: 45.2s, 3m 12s, 1h 05m."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


__all__ = [
    "logger",
    "log_scraper_start",
    "log_scraper_end",
    "log_state_start",
    "log_state_end",
    "log_search_start",
    "log_search_end",
    "log_db_summary",
    "log_task",
]
