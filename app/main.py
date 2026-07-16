"""Punto de entrada del scraper (fase Google Places -> Supabase).

Ejemplos:

    # Pipeline completo (50 estados x 20 búsquedas)
    python -m app.main

    # Modo de prueba: 2 estados x 3 búsquedas
    python -m app.main --states 2 --queries 3

    # Un estado específico con todas las búsquedas
    python -m app.main --state Florida

    # Una consulta específica en un estado específico
    python -m app.main --state Florida --query "baseball academy"

    # Probar Google Places sin escribir en Supabase
    python -m app.main --states 1 --queries 2 --dry-run
"""

import argparse
import sys

from app.config.search_queries import SEARCH_QUERIES
from app.config.states import STATES
from app.services.business_pipeline import (
    run_pipeline,
    FileCheckpoint,
    NoCheckpoint,
)
from app.utils.logger import logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scraper de negocios de baseball/softball (Google Places)."
    )
    parser.add_argument(
        "--states", type=int, metavar="N",
        help="Limitar a los primeros N estados (modo de prueba).",
    )
    parser.add_argument(
        "--queries", type=int, metavar="N",
        help="Limitar a las primeras N búsquedas (modo de prueba).",
    )
    parser.add_argument(
        "--state", type=str, metavar="NOMBRE",
        help="Ejecutar únicamente este estado (ej. Florida).",
    )
    parser.add_argument(
        "--query", type=str, metavar="TEXTO",
        help="Ejecutar únicamente esta búsqueda (ej. 'baseball academy').",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Buscar y parsear sin escribir en Supabase.",
    )
    parser.add_argument(
        "--reset-checkpoint", action="store_true",
        help="Borrar el checkpoint y empezar desde la primera búsqueda.",
    )
    return parser.parse_args()


def resolve_states(args: argparse.Namespace) -> list[str]:
    if args.state:
        matches = [s for s in STATES if s.lower() == args.state.lower()]
        if not matches:
            logger.error(f"Estado no válido: '{args.state}'")
            sys.exit(1)
        return matches
    if args.states:
        return STATES[: args.states]
    return STATES


def resolve_queries(args: argparse.Namespace) -> list[str]:
    if args.query:
        return [args.query]
    if args.queries:
        return SEARCH_QUERIES[: args.queries]
    return SEARCH_QUERIES


def main() -> None:
    args = parse_args()

    if args.dry_run:
        # dry-run no escribe en Supabase, tampoco debe marcar checkpoints
        checkpoint = NoCheckpoint()
    else:
        checkpoint = FileCheckpoint()
        if args.reset_checkpoint:
            checkpoint.clear()

    stats = run_pipeline(
        states=resolve_states(args),
        queries=resolve_queries(args),
        dry_run=args.dry_run,
        checkpoint=checkpoint,
    )
    sys.exit(1 if stats.completed == 0 and stats.errors > 0 else 0)


if __name__ == "__main__":
    main()
