"""Limpieza única: elimina de Supabase los negocios que hoy serían
descartados por el filtro de BLOCKED_KEYWORDS (entraron antes de crearlo).

Uso:

    # Ver qué se eliminaría (no borra nada)
    python -m scripts.cleanup_blocked

    # Eliminar de verdad
    python -m scripts.cleanup_blocked --apply
"""

import argparse

from app.database import supabase_client
from app.database.models import Business
from app.google.places_search import blocked_reason
from app.utils.logger import logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Limpieza de negocios bloqueados.")
    parser.add_argument(
        "--apply", action="store_true",
        help="Eliminar de verdad. Sin este flag solo muestra qué borraría.",
    )
    args = parser.parse_args()

    rows = supabase_client.get_all_for_audit()
    logger.info(f"Auditando {len(rows)} negocios...")

    blocked: list[tuple[str, str, str]] = []  # (place_id, nombre, keyword)
    for row in rows:
        business = Business(
            place_id=row["place_id"],
            business_name=row.get("business_name") or "",
            google_category=row.get("google_category"),
        )
        reason = blocked_reason(business)
        if reason:
            blocked.append((row["place_id"], business.business_name, reason))

    if not blocked:
        logger.success("No hay negocios bloqueados que limpiar.")
        return

    logger.warning(f"{len(blocked)} negocios coinciden con keywords bloqueadas:")
    for place_id, name, reason in blocked:
        logger.warning(f"  - '{name}' (keyword: {reason})")

    if not args.apply:
        logger.info(
            "Dry-run: no se eliminó nada. "
            "Ejecuta con --apply para eliminar estos registros."
        )
        return

    deleted = supabase_client.delete_by_place_ids([b[0] for b in blocked])
    logger.success(f"Eliminados {deleted} negocios de Supabase.")


if __name__ == "__main__":
    main()
