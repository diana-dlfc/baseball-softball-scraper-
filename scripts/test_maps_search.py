"""Prueba del motor de búsqueda Google Maps (Playwright).

Uso:

    python -m scripts.test_maps_search
    python -m scripts.test_maps_search "batting cage" Texas
"""

import sys

from app.search import google_maps_search
from app.utils.logger import logger, log_task


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "baseball academy"
    state = sys.argv[2] if len(sys.argv) > 2 else "Florida"

    with log_task(f"Google Maps: '{query}' en {state}"):
        businesses = google_maps_search.search(query, state)

    logger.success("-" * 60)
    logger.success(f"Negocios encontrados: {len(businesses)}")
    for b in businesses[:10]:
        logger.success(
            f"  {b.business_name} | {b.address or 'sin dirección'} | "
            f"{b.phone or 'sin tel'} | {b.website or 'sin web'} | "
            f"id: {b.place_id[:25]}"
        )
    if len(businesses) > 10:
        logger.success(f"  ... y {len(businesses) - 10} más")
    logger.success("-" * 60)


if __name__ == "__main__":
    main()
