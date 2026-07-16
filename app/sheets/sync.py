"""Sincronización Supabase -> Google Sheets.

Crea una pestaña por estado (en orden alfabético, ej. "AL — Alabama")
con los negocios de ese estado. Solo exporta negocios de USA.
Por defecto excluye los category='Irrelevant'; con --all los incluye.
Re-ejecutable: cada corrida reemplaza el contenido de las pestañas.

Uso:

    python -m app.sheets.sync
    python -m app.sheets.sync --all
    python -m app.sheets.sync --state Florida     # solo un estado
"""

import argparse
import time

from app.config.states import STATES, STATE_ABBR
from app.database import supabase_client
from app.database.models import Business
from app.sheets.google_sheets import SheetsClient
from app.utils.logger import logger, log_task

HEADER = [
    "Business Name", "City", "State", "Address",
    "Baseball", "Softball", "Phone", "Url Google Maps",
    "Indoor", "Outdoor", "Website", "Email", "Facebook",
    "Instagram", "Youtube", "Tiktok", "Owner", "Rating", "Reviews",
]

# Variantes aceptadas como Estados Unidos (se filtró Canadá y otros)
USA_VALUES = {"usa", "us", "united states", "estados unidos", "ee. uu."}

# Pausa entre pestañas: ~4 escrituras/pestaña vs límite de 60/minuto
PAUSE_BETWEEN_TABS = 4.0


def _si(value: bool | None) -> str:
    """True -> 'Si'; False o None -> vacío."""
    return "Si" if value else ""


def business_to_row(business: Business) -> list:
    """Convierte un Business en una fila con el orden de HEADER."""
    return [
        business.business_name or "",
        business.city or "",
        STATE_ABBR.get(business.state or "", business.state or ""),
        business.address or "",
        _si(business.baseball),
        _si(business.softball),
        business.phone or "",
        business.google_maps_url or "",
        _si(business.indoor),
        _si(business.outdoor),
        business.website or "",
        business.email or "",
        business.facebook or "",
        business.instagram or "",
        business.youtube or "",
        business.tiktok or "",
        business.owner or "",
        business.rating if business.rating is not None else "",
        business.reviews if business.reviews is not None else "",
    ]


def _is_usa(business: Business) -> bool:
    if not business.country:
        return True  # sin país: lo dejamos pasar (las búsquedas fueron en USA)
    return business.country.strip().lower() in USA_VALUES


def sync_to_sheets(
    include_all: bool = False, only_state: str | None = None
) -> int:
    """Exporta una pestaña por estado. Devuelve el total exportado."""
    businesses = supabase_client.get_all_businesses()
    logger.info(f"Total en Supabase: {len(businesses)}")

    filtered = [b for b in businesses if _is_usa(b)]
    dropped_country = len(businesses) - len(filtered)
    if dropped_country:
        logger.info(f"Excluidos por país (no-USA): {dropped_country}")

    if not include_all:
        filtered = [b for b in filtered if b.category != "Irrelevant"]

    by_state: dict[str, list[Business]] = {}
    for business in filtered:
        if business.state in STATE_ABBR:
            by_state.setdefault(business.state, []).append(business)

    states = [only_state] if only_state else STATES
    client = SheetsClient()
    exported = 0

    for state in states:
        state_businesses = by_state.get(state, [])
        if not state_businesses:
            logger.debug(f"{state}: sin negocios, se omite")
            continue

        state_businesses.sort(key=lambda b: (b.business_name or "").lower())
        rows = [business_to_row(b) for b in state_businesses]
        tab_name = f"{STATE_ABBR[state]} — {state}"

        client.write_table(tab_name, HEADER, rows)
        exported += len(rows)
        time.sleep(PAUSE_BETWEEN_TABS)

    return exported


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exportar negocios de Supabase a Google Sheets (una pestaña por estado)."
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Incluir también los marcados como Irrelevant.",
    )
    parser.add_argument(
        "--state", type=str, metavar="NOMBRE",
        help="Exportar solo este estado (ej. Florida).",
    )
    args = parser.parse_args()

    with log_task("Export a Google Sheets"):
        exported = sync_to_sheets(include_all=args.all, only_state=args.state)

    logger.success(f"Exportados {exported} negocios a Google Sheets")


if __name__ == "__main__":
    main()
