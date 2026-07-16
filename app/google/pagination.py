"""Paginación de Google Places (New).

Responsabilidad única: recorrer todas las páginas de una búsqueda de texto
(máximo 3 páginas / 60 resultados, límite de Google) y devolver la lista
completa de lugares crudos, sin duplicados por place_id.

No conoce Business, Supabase ni el pipeline.
"""

import time
from typing import Any

from app.config.settings import REQUEST_DELAY
from app.google.places_client import (
    PlacesClient,
    PlacesApiError,
    QuotaExceededError,
)
from app.utils.logger import logger

# Límite impuesto por Google Places: 3 páginas de 20 = 60 resultados
MAX_PAGES = 3


def fetch_all_pages(
    query: str,
    client: PlacesClient | None = None,
    max_pages: int = MAX_PAGES,
) -> list[dict[str, Any]]:
    """Obtiene todas las páginas disponibles de una búsqueda de texto.

    Devuelve la lista acumulada de lugares (JSON crudo de Google),
    sin duplicados por place_id. Si una página falla, registra el error
    y devuelve lo acumulado hasta ese momento.
    """
    client = client or PlacesClient()
    places: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    page_token: str | None = None
    start = time.perf_counter()

    for page in range(1, max_pages + 1):
        if page_token:
            # Google exige una pausa antes de consumir el nextPageToken
            time.sleep(REQUEST_DELAY)

        try:
            response = client.search_text(query, page_token=page_token)
        except QuotaExceededError:
            # Cuota diaria agotada: se propaga para abortar el pipeline
            raise
        except PlacesApiError:
            logger.exception(
                f"Página {page} falló para '{query}'. "
                f"Devolviendo {len(places)} resultados acumulados."
            )
            break

        page_places = response.get("places", [])
        new_count = 0
        for place in page_places:
            place_id = place.get("id")
            if place_id and place_id not in seen_ids:
                seen_ids.add(place_id)
                places.append(place)
                new_count += 1

        logger.debug(
            f"'{query}' | página {page}: {len(page_places)} resultados "
            f"({new_count} nuevos) | acumulado: {len(places)}"
        )

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    elapsed = time.perf_counter() - start
    logger.info(
        f"'{query}' | paginación completa: {len(places)} lugares "
        f"en {page} página(s) ({elapsed:.1f}s)"
    )
    return places
