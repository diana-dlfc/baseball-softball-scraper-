"""Gestión del navegador Playwright: ciclo de vida, concurrencia y páginas.

Uso:

    async with PlaywrightManager() as manager:
        async with manager.page() as page:
            await page.goto("https://ejemplo.com")

El semáforo interno limita las páginas simultáneas a MAX_CONCURRENT_PAGES.
Las imágenes, fuentes y media se bloquean para acelerar la carga.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import async_playwright, Browser, Page, Playwright

from app.config.settings import (
    HEADLESS,
    MAX_CONCURRENT_PAGES,
    PLAYWRIGHT_TIMEOUT,
)
from app.utils.logger import logger

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Recursos que no aportan al scraping de texto/links y frenan la carga
BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}

# Flags OBLIGATORIOS para Chromium en Docker/Railway:
# /dev/shm está limitado a 64MB en Docker y Chromium crashea sin estos.
# En local no estorban.
CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-blink-features=AutomationControlled",
]


class PlaywrightManager:
    """Administra un navegador Chromium compartido y sus páginas."""

    def __init__(
        self,
        headless: bool = HEADLESS,
        max_concurrent_pages: int = MAX_CONCURRENT_PAGES,
    ) -> None:
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._semaphore = asyncio.Semaphore(max_concurrent_pages)

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=CHROMIUM_ARGS,
        )
        logger.debug("Navegador Chromium iniciado")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.debug("Navegador Chromium cerrado")

    async def __aenter__(self) -> "PlaywrightManager":
        await self.start()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.stop()

    @asynccontextmanager
    async def page(self) -> AsyncIterator[Page]:
        """Entrega una página nueva en un contexto aislado.

        Respeta el límite de concurrencia y cierra el contexto al salir.
        """
        if self._browser is None:
            raise RuntimeError(
                "PlaywrightManager no iniciado. Usa 'async with' o start()."
            )

        async with self._semaphore:
            context = await self._browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1366, "height": 768},
                locale="en-US",
            )
            await context.route("**/*", _block_heavy_resources)
            page = await context.new_page()
            page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
            try:
                yield page
            finally:
                await context.close()


async def _block_heavy_resources(route) -> None:
    if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
        await route.abort()
    else:
        await route.continue_()
