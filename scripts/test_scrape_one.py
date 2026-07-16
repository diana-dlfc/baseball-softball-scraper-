"""Prueba de la capa de scraping con un solo website.

Uso:

    python -m scripts.test_scrape_one https://bpbtraining.com
    python -m scripts.test_scrape_one   (usa un sitio de ejemplo)
"""

import asyncio
import sys

from app.scraping.contact_extractor import (
    extract_contact_info,
    WebsiteUnreachable,
)
from app.scraping.playwright_manager import PlaywrightManager
from app.utils.logger import logger, log_task

DEFAULT_URL = "https://bpbtraining.com"


async def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

    async with PlaywrightManager() as manager:
        with log_task(f"Scraping de {url}"):
            try:
                info = await extract_contact_info(manager, url)
            except WebsiteUnreachable as exc:
                logger.error(str(exc))
                return

    logger.success("-" * 50)
    logger.success(f"Páginas visitadas : {info.pages_visited}")
    logger.success(f"Email             : {info.email or 'no encontrado'}")
    logger.success(f"Facebook          : {info.facebook or 'no encontrado'}")
    logger.success(f"Instagram         : {info.instagram or 'no encontrado'}")
    logger.success(f"TikTok            : {info.tiktok or 'no encontrado'}")
    logger.success(f"YouTube           : {info.youtube or 'no encontrado'}")
    logger.success(f"Owner             : {info.owner or 'no encontrado'}")
    logger.success("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
