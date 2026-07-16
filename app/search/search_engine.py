"""Motor de búsqueda unificado: decide entre Google Places y Google Maps.

Único módulo que conoce ambos motores. El resto del proyecto solo llama
a SearchEngine.search(query, state) y recibe list[Business].

Modos (settings.SEARCH_ENGINE o variable de entorno SEARCH_ENGINE):
    auto   -> Places; si la cuota diaria se agota, cambia a Maps y sigue
    places -> solo Places (la cuota agotada aborta el pipeline, como antes)
    maps   -> solo Maps (Playwright)
"""

from app.config.settings import SEARCH_ENGINE
from app.database.models import Business
from app.google.places_client import QuotaExceededError
from app.search import google_maps_search, google_places_search
from app.utils.logger import logger

VALID_MODES = ("auto", "places", "maps")


class SearchEngine:
    """Selecciona el motor y hace el fallback automático en modo auto."""

    def __init__(self, mode: str = SEARCH_ENGINE) -> None:
        if mode not in VALID_MODES:
            raise ValueError(
                f"SEARCH_ENGINE inválido: '{mode}'. Usa {VALID_MODES}"
            )
        self.mode = mode
        self._using_maps = mode == "maps"
        logger.info(f"Motor de búsqueda: {mode}")

    @property
    def active_engine(self) -> str:
        return "maps" if self._using_maps else "places"

    def search(self, query: str, state: str) -> list[Business]:
        """Busca con el motor activo. En modo auto, cae a Maps sin cuota."""
        if self._using_maps:
            return google_maps_search.search(query, state)

        try:
            return google_places_search.search(query, state)
        except QuotaExceededError:
            if self.mode != "auto":
                raise
            logger.warning(
                "Cuota diaria de Google Places agotada. Cambiando "
                "automáticamente al motor Google Maps (Playwright). "
                "El pipeline continúa sin interrupción."
            )
            self._using_maps = True
            return google_maps_search.search(query, state)
