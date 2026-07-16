"""Búsqueda y guardado de negocios.

Responsabilidad única: para un (query, estado) dado,
    1. obtiene los Business desde el motor de búsqueda activo
       (SearchEngine decide entre Places API y Google Maps),
    2. filtra los bloqueados por keywords,
    3. guarda el lote en Supabase con 3 peticiones en total.

No conoce qué motor se usó: recibe list[Business] y punto.
"""

import re
from typing import Any

from app.config.categories import BLOCKED_KEYWORDS, WHITELIST_KEYWORDS
from app.database.models import Business
from app.database import supabase_client
from app.google.places_client import QuotaExceededError
from app.search.search_engine import SearchEngine
from app.utils.logger import logger, log_search_start, log_search_end, log_db_summary

# Campos que la búsqueda puede refrescar en negocios ya existentes.
# Nunca se tocan los campos enriquecidos (email, redes, owner, status, scraped).
VOLATILE_FIELDS = (
    "business_name",
    "address",
    "phone",
    "website",
    "rating",
    "reviews",
    "google_maps_url",
)

# Regex con límites de palabra: "park" bloquea "City Park" pero no "Parker"
_BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in BLOCKED_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

_engine: SearchEngine | None = None


def _default_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        _engine = SearchEngine()
    return _engine


def blocked_reason(business: Business) -> str | None:
    """Devuelve la keyword bloqueada encontrada en nombre/categoría, o None."""
    name = (business.business_name or "").lower()
    if any(allowed in name for allowed in WHITELIST_KEYWORDS):
        return None
    category = (business.google_category or "").replace("_", " ")
    match = _BLOCKED_PATTERN.search(f"{name} | {category}")
    return match.group(1).lower() if match else None


def save_businesses(businesses: list[Business]) -> tuple[int, int]:
    """Guarda un lote completo de Business en 3 peticiones a Supabase.

    Devuelve (insertados, actualizados). Los negocios que ya existen
    solo reciben actualización de VOLATILE_FIELDS para no pisar los
    campos enriquecidos por Playwright o la IA.
    """
    if not businesses:
        return 0, 0

    existing_ids = supabase_client.get_existing_place_ids(
        [b.place_id for b in businesses]
    )

    new_rows: list[dict[str, Any]] = []
    update_rows: list[dict[str, Any]] = []

    for business in businesses:
        if business.place_id in existing_ids:
            row = business.to_dict()
            update_rows.append(
                {"place_id": business.place_id}
                | {f: row[f] for f in VOLATILE_FIELDS if f in row}
            )
        else:
            new_rows.append(business.to_dict())

    inserted = supabase_client.bulk_upsert(new_rows, set_created_at=True)
    updated = supabase_client.bulk_upsert(update_rows)
    return inserted, updated


def search_and_save(
    query: str,
    state: str,
    dry_run: bool = False,
    engine: SearchEngine | None = None,
) -> tuple[int, int, int]:
    """Ejecuta una búsqueda completa y guarda los resultados.

    Devuelve (encontrados, insertados, actualizados).
    Con dry_run=True busca y filtra pero NO escribe en Supabase.
    """
    log_search_start(query, state)
    engine = engine or _default_engine()

    try:
        found = engine.search(query, state)
    except QuotaExceededError:
        raise  # solo llega aquí en modo 'places'; el pipeline aborta
    except Exception:
        logger.exception(f"[{state}] Falló la búsqueda '{query}'")
        return 0, 0, 0

    log_search_end(query, state, len(found))

    businesses: list[Business] = []
    skipped = 0
    for business in found:
        reason = blocked_reason(business)
        if reason:
            skipped += 1
            logger.debug(
                f"[{state}] Descartado por keyword '{reason}': "
                f"{business.business_name}"
            )
            continue
        businesses.append(business)

    if skipped:
        logger.info(f"[{state}] {skipped} negocios descartados por filtro")

    if dry_run:
        logger.info(
            f"[{state}] dry-run: {len(businesses)} negocios listos, "
            "NO guardados en Supabase"
        )
        return len(found), 0, 0

    try:
        inserted, updated = save_businesses(businesses)
    except Exception:
        # Se propaga: el pipeline la cuenta como fallida y NO la marca en el
        # checkpoint, así se reintenta en la próxima ejecución sin perder datos.
        logger.exception(f"[{state}] Error guardando el lote de '{query}'")
        raise

    log_db_summary(inserted, updated, skipped)
    return len(found), inserted, updated
