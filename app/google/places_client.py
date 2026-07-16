"""Cliente HTTP para Google Places API (New) v1.

Responsabilidad única: comunicarse con la API de Google Places.
No conoce Business, Supabase ni Playwright. Devuelve el JSON crudo de Google.
"""

from typing import Any

import requests

from app.config.settings import (
    GOOGLE_PLACES_API_KEY,
    GOOGLE_PLACES_PAGE_SIZE,
    GOOGLE_TIMEOUT,
)

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.googleMapsUri",
        "places.primaryType",
        "places.types",
        "nextPageToken",
    ]
)


class PlacesApiError(Exception):
    """Error devuelto por la API de Google Places o por la conexión HTTP."""


class QuotaExceededError(PlacesApiError):
    """La cuota diaria de la API se agotó: no tiene sentido reintentar hoy."""


class PlacesClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or GOOGLE_PLACES_API_KEY
        if not self.api_key:
            raise EnvironmentError(
                "Falta GOOGLE_PLACES_API_KEY en el archivo .env"
            )

    def search_text(
        self, query: str, page_token: str | None = None
    ) -> dict[str, Any]:
        """Ejecuta una búsqueda de texto y devuelve el JSON crudo de Google.

        Si se pasa page_token, solicita la página siguiente de una
        búsqueda anterior (paginación con nextPageToken).
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        body: dict[str, Any] = {
            "textQuery": query,
            "pageSize": GOOGLE_PLACES_PAGE_SIZE,
        }
        if page_token:
            body["pageToken"] = page_token

        try:
            response = requests.post(
                SEARCH_TEXT_URL,
                headers=headers,
                json=body,
                timeout=GOOGLE_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise PlacesApiError(f"Error de conexión con Google Places: {exc}") from exc

        if response.status_code != 200:
            if response.status_code == 429 and "per day" in response.text:
                raise QuotaExceededError(
                    "Cuota diaria de Google Places agotada "
                    "(SearchTextRequest per day). Se reinicia a medianoche, "
                    "hora del Pacífico."
                )
            raise PlacesApiError(
                f"Google Places respondió {response.status_code}: {response.text[:300]}"
            )

        data = response.json()

        if "error" in data:
            error = data["error"]
            raise PlacesApiError(
                f"Error de la API de Google Places "
                f"({error.get('status', 'UNKNOWN')}): {error.get('message', '')}"
            )

        return data
