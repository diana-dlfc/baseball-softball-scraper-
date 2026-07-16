"""Prueba de extremo a extremo de places_search.

Ejecutar desde la raíz del proyecto:

    python -m tests.test_places_search
"""

import time

from app.google.places_search import search_and_save
from app.utils.logger import logger, log_task


def main() -> None:
    state = "Florida"
    query = "baseball training facility"

    start = time.perf_counter()

    with log_task(f"Prueba: '{query}' en {state}"):
        found, inserted, updated = search_and_save(query, state)

    elapsed = time.perf_counter() - start

    logger.success("-" * 50)
    logger.success(f"Google Places devolvió : {found} negocios")
    logger.success(f"Insertados en Supabase : {inserted}")
    logger.success(f"Actualizados           : {updated}")
    logger.success(f"Tiempo total           : {elapsed:.1f}s")
    logger.success("-" * 50)


if __name__ == "__main__":
    main()
