"""Motor de búsqueda 1: Google Places API (New).

Envuelve la paginación existente y convierte los resultados a Business.
Puede lanzar QuotaExceededError; search_engine decide qué hacer con eso.
"""

from typing import Any

from app.config.constants import Status
from app.database.models import Business
from app.google.pagination import fetch_all_pages
from app.utils.logger import logger


def build_text_query(query: str, state: str) -> str:
    """Combina búsqueda y estado en el formato que espera Google."""
    return f"{query} in {state}, USA"


def search(query: str, state: str) -> list[Business]:
    """Busca con Google Places y devuelve la lista de Business."""
    source_query = build_text_query(query, state)
    places = fetch_all_pages(source_query)

    businesses: list[Business] = []
    for place in places:
        try:
            businesses.append(parse_place(place, source_query, state))
        except Exception:
            logger.exception(
                f"[{state}] Error parseando place_id="
                f"{place.get('id', 'desconocido')}"
            )
    return businesses


def parse_place(place: dict[str, Any], source_query: str, state: str) -> Business:
    """Convierte un resultado crudo de Google Places en un Business."""
    address = place.get("formattedAddress")
    city, country = _parse_city_country(address)
    location = place.get("location", {})

    return Business(
        place_id=place["id"],
        business_name=place.get("displayName", {}).get("text", ""),
        source_query=source_query,
        google_category=place.get("primaryType"),
        google_maps_url=place.get("googleMapsUri"),
        address=address,
        city=city,
        state=state,
        country=country,
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        phone=place.get("nationalPhoneNumber"),
        website=place.get("websiteUri"),
        rating=place.get("rating"),
        reviews=place.get("userRatingCount"),
        scraped=False,
        status=Status.PENDING,
    )


def _parse_city_country(address: str | None) -> tuple[str | None, str | None]:
    """Extrae ciudad y país de una dirección formateada.

    Ejemplo: '501 NE 48th St, Pompano Beach, FL 33064, USA'
             -> ('Pompano Beach', 'USA')
    """
    if not address:
        return None, None
    parts = [p.strip() for p in address.split(",")]
    if len(parts) < 3:
        return None, parts[-1] if parts else None
    return parts[-3], parts[-1]
