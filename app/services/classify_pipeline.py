"""Pipeline de clasificación IA.

Toma de Supabase los negocios sin categoría, los clasifica con el LLM
y guarda: categoría final, indoor/outdoor, baseball/softball.
Los no relevantes quedan con category='Irrelevant' (no se borran, para
poder auditarlos después).

La columna `category` funciona como checkpoint natural: re-ejecutar
continúa con los que faltan.

Uso:

    python -m app.services.classify_pipeline               # todos
    python -m app.services.classify_pipeline --limit 5     # prueba
    python -m app.services.classify_pipeline --limit 5 --dry-run
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.ai.classifier import classify_business
from app.config.settings import CLASSIFY_WORKERS
from app.database import supabase_client
from app.database.models import Business
from app.utils.logger import logger, _format_elapsed

BATCH_SIZE = 50


@dataclass
class ClassifyStats:
    processed: int = 0
    classified: int = 0
    relevant: int = 0
    irrelevant: int = 0
    failed: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_at


def run_classify_pipeline(
    limit: int | None = None, dry_run: bool = False
) -> ClassifyStats:
    """Clasifica negocios pendientes hasta agotarlos (o hasta limit)."""
    stats = ClassifyStats()
    logger.success(f"CLASIFICACIÓN IA INICIADA | dry_run={dry_run}")

    while True:
        batch_limit = BATCH_SIZE
        if limit is not None:
            batch_limit = min(BATCH_SIZE, limit - stats.processed)
            if batch_limit <= 0:
                break

        batch = supabase_client.get_unclassified_businesses(batch_limit)
        if not batch:
            logger.info("No quedan negocios sin clasificar")
            break

        batch_failed_before = stats.failed
        with ThreadPoolExecutor(max_workers=CLASSIFY_WORKERS) as pool:
            list(pool.map(
                lambda b: _classify_one(b, stats, dry_run), batch
            ))

        # Si el lote completo falló (LLM caído / sin créditos), abortamos:
        # reintentar el mismo lote en bucle sería infinito.
        if stats.failed - batch_failed_before == len(batch):
            logger.critical(
                "Todo el lote falló. Revisa el LLM (créditos/rate limit). "
                "Re-ejecutar continuará con los pendientes."
            )
            break

        logger.info(
            f"Progreso: {stats.processed} procesados | "
            f"{stats.relevant} relevantes | {stats.irrelevant} irrelevantes | "
            f"{stats.failed} fallidos | "
            f"transcurrido: {_format_elapsed(stats.elapsed_seconds)}"
        )

        if dry_run:
            # en dry-run no se marca nada: el mismo lote volvería infinito
            break

    _log_summary(stats, dry_run)
    return stats


def _classify_one(business: Business, stats: ClassifyStats, dry_run: bool) -> None:
    """Clasifica y guarda un negocio. Corre dentro del pool de workers."""
    result = classify_business(business)
    stats.processed += 1
    time.sleep(1.0)  # ritmo ~27/min: bajo el límite de 30 RPM del proveedor

    if result is None:
        stats.failed += 1
        return

    stats.classified += 1
    stats.relevant += result.relevant
    stats.irrelevant += not result.relevant
    logger.info(
        f"'{business.business_name}' -> "
        f"{result.category if result.relevant else 'IRRELEVANTE'} | "
        f"indoor={result.indoor} outdoor={result.outdoor} | "
        f"baseball={result.baseball} softball={result.softball}"
    )
    if not dry_run:
        supabase_client.update_business(
            business.place_id, result.to_update_dict()
        )


def _log_summary(stats: ClassifyStats, dry_run: bool) -> None:
    logger.success("-" * 60)
    logger.success("RESUMEN DE CLASIFICACIÓN" + (" (DRY-RUN)" if dry_run else ""))
    logger.success(f"Procesados   : {stats.processed}")
    logger.success(f"Clasificados : {stats.classified}")
    logger.success(f"Relevantes   : {stats.relevant}")
    logger.success(f"Irrelevantes : {stats.irrelevant}")
    logger.success(f"Fallidos     : {stats.failed}")
    logger.success(f"Tiempo total : {_format_elapsed(stats.elapsed_seconds)}")
    logger.success("-" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clasificación IA de negocios.")
    parser.add_argument(
        "--limit", type=int, metavar="N",
        help="Clasificar máximo N negocios (modo de prueba).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Clasificar y mostrar resultados sin escribir en Supabase.",
    )
    args = parser.parse_args()
    run_classify_pipeline(args.limit, args.dry_run)


if __name__ == "__main__":
    main()
