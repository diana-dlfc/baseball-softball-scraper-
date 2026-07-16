"""Pipeline de enriquecimiento: scrapea los websites de negocios pendientes.

Toma de Supabase los negocios con website y scraped=false/null, visita cada
sitio con Playwright (concurrencia limitada por MAX_CONCURRENT_PAGES),
extrae email/redes/owner y guarda el resultado:

    - Éxito  -> mark_scraped() con los datos encontrados (status=completed)
    - Fallo  -> mark_error() con el motivo (status=error)

La columna `scraped` funciona como checkpoint natural: si el proceso se
interrumpe, re-ejecutar continúa con los que faltan.

Uso:

    python -m app.services.scrape_pipeline                # todos los pendientes
    python -m app.services.scrape_pipeline --limit 10     # prueba con 10
"""

import argparse
import asyncio
import time
from dataclasses import dataclass, field

from app.database import supabase_client
from app.database.models import Business
from app.scraping.contact_extractor import (
    extract_contact_info,
    WebsiteUnreachable,
)
from app.scraping.playwright_manager import PlaywrightManager
from app.utils.logger import logger, _format_elapsed

BATCH_SIZE = 25

# Límite duro por negocio: nada puede colgar el pipeline más de esto
BUSINESS_TIMEOUT = 120  # segundos

# Reinicio preventivo del navegador: Chromium acumula memoria y termina
# muriendo en corridas largas; una instancia fresca cada N negocios lo evita
BROWSER_RESTART_AFTER = 500


@dataclass
class ScrapeStats:
    processed: int = 0
    ok: int = 0
    unreachable: int = 0
    failed: int = 0
    emails: int = 0
    socials: int = 0
    owners: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_at


async def _process_business(
    manager: PlaywrightManager, business: Business, stats: ScrapeStats
) -> None:
    """Scrapea un negocio y persiste el resultado. Nunca lanza excepción."""
    try:
        info = await asyncio.wait_for(
            extract_contact_info(manager, business.website),
            timeout=BUSINESS_TIMEOUT,
        )
        data = {
            key: value
            for key, value in {
                "email": info.email,
                "facebook": info.facebook,
                "instagram": info.instagram,
                "tiktok": info.tiktok,
                "youtube": info.youtube,
                "owner": info.owner,
            }.items()
            if value  # solo campos encontrados: no pisar con None
        }
        await asyncio.to_thread(
            supabase_client.mark_scraped, business.place_id, data
        )
        stats.ok += 1
        stats.emails += bool(info.email)
        stats.socials += bool(
            info.facebook or info.instagram or info.tiktok or info.youtube
        )
        stats.owners += bool(info.owner)
    except asyncio.TimeoutError:
        logger.warning(f"Timeout duro ({BUSINESS_TIMEOUT}s): {business.website}")
        await asyncio.to_thread(
            supabase_client.mark_error,
            business.place_id,
            f"Timeout duro de {BUSINESS_TIMEOUT}s",
        )
        stats.unreachable += 1
    except WebsiteUnreachable as exc:
        await asyncio.to_thread(
            supabase_client.mark_error, business.place_id, str(exc)
        )
        stats.unreachable += 1
    except Exception as exc:
        logger.exception(f"Error scrapeando {business.website}")
        await asyncio.to_thread(
            supabase_client.mark_error,
            business.place_id,
            f"{type(exc).__name__}: {exc}",
        )
        stats.failed += 1
    finally:
        stats.processed += 1


async def run_scrape_pipeline(
    limit: int | None = None, batch_size: int = BATCH_SIZE
) -> ScrapeStats:
    """Procesa negocios pendientes por lotes hasta agotarlos (o hasta limit)."""
    stats = ScrapeStats()
    logger.success("SCRAPING DE WEBSITES INICIADO")

    keep_going = True
    while keep_going:
        processed_with_this_browser = 0

        async with PlaywrightManager() as manager:
            while processed_with_this_browser < BROWSER_RESTART_AFTER:
                remaining = batch_size
                if limit is not None:
                    remaining = min(batch_size, limit - stats.processed)
                    if remaining <= 0:
                        keep_going = False
                        break

                batch = await asyncio.to_thread(
                    supabase_client.get_pending_businesses, remaining
                )
                if not batch:
                    logger.info("No quedan negocios pendientes")
                    keep_going = False
                    break

                await asyncio.gather(
                    *(_process_business(manager, b, stats) for b in batch)
                )
                processed_with_this_browser += len(batch)
                logger.info(
                    f"Progreso: {stats.processed} procesados | "
                    f"{stats.ok} ok | {stats.unreachable} inaccesibles | "
                    f"{stats.failed} errores | "
                    f"transcurrido: {_format_elapsed(stats.elapsed_seconds)}"
                )

        if keep_going:
            logger.info(
                f"Reinicio preventivo del navegador "
                f"(cada {BROWSER_RESTART_AFTER} negocios)"
            )

    _log_summary(stats)
    return stats


def _log_summary(stats: ScrapeStats) -> None:
    logger.success("-" * 60)
    logger.success("RESUMEN DEL SCRAPING")
    logger.success(f"Procesados            : {stats.processed}")
    logger.success(f"Exitosos              : {stats.ok}")
    logger.success(f"Sitios inaccesibles   : {stats.unreachable}")
    logger.success(f"Errores               : {stats.failed}")
    logger.success(f"Con email             : {stats.emails}")
    logger.success(f"Con alguna red social : {stats.socials}")
    logger.success(f"Con owner             : {stats.owners}")
    logger.success(f"Tiempo total          : {_format_elapsed(stats.elapsed_seconds)}")
    logger.success("-" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scraping de websites de negocios pendientes."
    )
    parser.add_argument(
        "--limit", type=int, metavar="N",
        help="Procesar máximo N negocios (modo de prueba).",
    )
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE, metavar="N",
        help=f"Tamaño de lote (default {BATCH_SIZE}).",
    )
    args = parser.parse_args()
    asyncio.run(run_scrape_pipeline(args.limit, args.batch_size))


if __name__ == "__main__":
    main()
