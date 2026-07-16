"""Cliente de Supabase para la tabla de negocios (baseball/softball scraper)."""

import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import create_client, Client

from app.config.constants import Status
from app.database.models import Business
from app.utils.retry import retry

load_dotenv()

# Nombre de la tabla en Supabase
TABLE = "businesses"

_client: Optional[Client] = None


def get_client() -> Client:
    """Devuelve una instancia única (singleton) del cliente de Supabase."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise EnvironmentError(
                "Faltan SUPABASE_URL o SUPABASE_KEY en el archivo .env"
            )
        _client = create_client(url, key)
    return _client


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Operaciones CRUD
# ---------------------------------------------------------------------------

@retry(times=3, delay=2)
def upsert_business(business: Business) -> Business:
    """Inserta o actualiza un negocio usando place_id como clave única."""
    data = business.to_dict()
    data["updated_at"] = _now()
    data.setdefault("created_at", _now())
    response = (
        get_client()
        .table(TABLE)
        .upsert(data, on_conflict="place_id")
        .execute()
    )
    return Business.from_dict(response.data[0]) if response.data else business


@retry(times=3, delay=2)
def get_by_place_id(place_id: str) -> Optional[Business]:
    """Busca un negocio por su place_id. Devuelve None si no existe."""
    response = (
        get_client()
        .table(TABLE)
        .select("*")
        .eq("place_id", place_id)
        .limit(1)
        .execute()
    )
    return Business.from_dict(response.data[0]) if response.data else None


def exists(place_id: str) -> bool:
    """True si el place_id ya está en la base de datos."""
    return get_by_place_id(place_id) is not None


@retry(times=3, delay=2)
def update_business(place_id: str, data: dict[str, Any]) -> Optional[Business]:
    """Actualiza campos puntuales de un negocio existente (update parcial)."""
    data["updated_at"] = _now()
    response = (
        get_client()
        .table(TABLE)
        .update(data)
        .eq("place_id", place_id)
        .execute()
    )
    return Business.from_dict(response.data[0]) if response.data else None


@retry(times=3, delay=2)
def get_existing_place_ids(place_ids: list[str]) -> set[str]:
    """Devuelve, en una sola consulta, cuáles de estos place_id ya existen."""
    if not place_ids:
        return set()
    response = (
        get_client()
        .table(TABLE)
        .select("place_id")
        .in_("place_id", place_ids)
        .execute()
    )
    return {row["place_id"] for row in (response.data or [])}


@retry(times=3, delay=2)
def bulk_upsert(rows: list[dict[str, Any]], set_created_at: bool = False) -> int:
    """Upsert masivo en una sola petición. Cada dict debe incluir place_id.

    Solo las columnas presentes en los dicts se insertan/actualizan;
    las demás no se tocan. Usa set_created_at=True solo para filas nuevas.
    """
    if not rows:
        return 0
    now = _now()
    for row in rows:
        row["updated_at"] = now
        if set_created_at:
            row.setdefault("created_at", now)
    response = (
        get_client()
        .table(TABLE)
        .upsert(rows, on_conflict="place_id")
        .execute()
    )
    return len(response.data or [])


@retry(times=3, delay=2)
def get_pending_businesses(limit: int = 50) -> list[Business]:
    """Negocios con website que aún no han sido procesados."""
    response = (
        get_client()
        .table(TABLE)
        .select("*")
        .not_.is_("website", "null")
        .or_("scraped.is.null,scraped.eq.false")
        .limit(limit)
        .execute()
    )
    return [Business.from_dict(row) for row in (response.data or [])]


def mark_scraped(place_id: str, data: Optional[dict[str, Any]] = None) -> None:
    """Marca un negocio como procesado y guarda los datos extraídos."""
    payload = data or {}
    payload.update(
        {
            "scraped": True,
            "status": Status.COMPLETED,
            "error": None,
            "last_scraped": _now(),
        }
    )
    update_business(place_id, payload)


def mark_error(place_id: str, error: str) -> None:
    """Registra un error de scraping para un negocio."""
    update_business(
        place_id,
        {
            "scraped": True,
            "status": Status.ERROR,
            "error": error[:500],
            "last_scraped": _now(),
        },
    )


@retry(times=3, delay=2)
def get_unclassified_businesses(limit: int = 50) -> list[Business]:
    """Negocios sin categoría asignada (pendientes de clasificación IA)."""
    response = (
        get_client()
        .table(TABLE)
        .select("*")
        .is_("category", "null")
        .limit(limit)
        .execute()
    )
    return [Business.from_dict(row) for row in (response.data or [])]


def delete_by_place_ids(place_ids: list[str]) -> int:
    """Elimina negocios por place_id. Devuelve cuántos borró."""
    if not place_ids:
        return 0
    response = (
        get_client()
        .table(TABLE)
        .delete()
        .in_("place_id", place_ids)
        .execute()
    )
    return len(response.data or [])


def get_all_businesses() -> list[Business]:
    """Todos los negocios de la tabla, paginando de 1000 en 1000."""
    businesses: list[Business] = []
    page_size = 1000
    offset = 0
    while True:
        response = (
            get_client()
            .table(TABLE)
            .select("*")
            .order("state")
            .order("business_name")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        businesses.extend(Business.from_dict(row) for row in batch)
        if len(batch) < page_size:
            return businesses
        offset += page_size


def get_all_for_audit() -> list[dict[str, Any]]:
    """Campos mínimos de todos los negocios, para auditorías/limpiezas."""
    rows: list[dict[str, Any]] = []
    page_size = 1000
    offset = 0
    while True:
        response = (
            get_client()
            .table(TABLE)
            .select("place_id,business_name,google_category")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size


def count_businesses() -> int:
    """Total de negocios en la tabla."""
    response = (
        get_client()
        .table(TABLE)
        .select("id", count="exact")
        .execute()
    )
    return response.count or 0


if __name__ == "__main__":
    # Prueba rápida de conexión: python -m app.database.supabase_client
    print("Conectando a Supabase...")
    print(f"Conexión OK. Negocios en la tabla '{TABLE}': {count_businesses()}")
