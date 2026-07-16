"""Debug: muestra todos los links de un sitio que mencionen redes sociales.

Uso:

    python -m scripts.debug_links https://bpbtraining.com
"""

import asyncio
import sys

from app.scraping.playwright_manager import PlaywrightManager
from app.scraping.website_scraper import scrape_website
from app.utils.logger import logger

SOCIAL_HINTS = ("facebook", "fb.", "instagram", "tiktok", "youtube", "youtu.be")


async def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://bpbtraining.com"

    async with PlaywrightManager() as manager:
        site = await scrape_website(manager, url)

    if site is None:
        logger.error(f"No se pudo cargar {url}")
        return

    logger.info(f"Total de links encontrados: {len(site.links)}")
    social_links = [
        link for link in sorted(site.links)
        if any(hint in link.lower() for hint in SOCIAL_HINTS)
    ]

    if not social_links:
        logger.warning("Ningún link contiene menciones de redes sociales")
    for link in social_links:
        logger.success(f"  {link}")


if __name__ == "__main__":
    asyncio.run(main())
