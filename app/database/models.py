"""Modelo de datos para la tabla `businesses` de Supabase."""

from dataclasses import dataclass, asdict, fields
from typing import Any, Optional


@dataclass
class Business:
    place_id: str
    business_name: str
    id: Optional[str] = None
    source_query: Optional[str] = None
    google_category: Optional[str] = None
    google_maps_url: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    youtube: Optional[str] = None
    category: Optional[str] = None
    indoor: bool = False
    outdoor: bool = False
    baseball: bool = False
    softball: bool = False
    rating: Optional[float] = None
    reviews: Optional[int] = None
    owner: Optional[str] = None
    scraped: bool = False
    status: Optional[str] = None
    error: Optional[str] = None
    last_scraped: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Diccionario listo para guardar en Supabase (sin campos None)."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Business":
        """Construye un Business desde un diccionario devuelto por Supabase."""
        valid_keys = {f.name for f in fields(Business)}
        return Business(**{k: v for k, v in data.items() if k in valid_keys})
