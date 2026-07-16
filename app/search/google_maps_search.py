"""Motor de búsqueda 2 (fallback): Google Maps scrapeado con Playwright.

Busca en google.com/maps, hace scroll del panel de resultados hasta
agotarlo (o llegar a MAX_RESULTS) y convierte cada tarjeta en un Business.

Identificador estable: intenta extraer el place_id real (ChIJ...) del link;
si no existe, usa el id hexadecimal de Maps; como último recurso, un hash
de nombre+dirección. Así el dedup por place_id sigue funcionando.
"""

import asyncio
import hashlib
import re
from typing import Any
from urllib.parse import quote_plus

from playwright.async_api import Error as PlaywrightError, TimeoutError

from app.config.constants import Status
from app.database.models import Business
from app.scraping.playwright_manager import PlaywrightManager
from app.search.google_places_search import build_text_query
from app.utils.logger import logger

MAPS_SEARCH_URL = "https://www.google.com/maps/search/{}?hl=en"
MAX_RESULTS = 60          # paridad con el límite de Places API
MAX_SCROLLS = 30
SCROLL_PAUSE_MS = 1200

# place_id real (mismo formato que Places API) o id hexadecimal de Maps
CHIJ_PATTERN = re.compile(r"(ChIJ[A-Za-z0-9_-]{10,})")
HEX_PATTERN = re.compile(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)")
PHONE_PATTERN = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}")

# JS que extrae los datos de cada tarjeta del panel de resultados
EXTRACT_JS = """
() => Array.from(document.querySelectorAll('a.hfpxzc')).map(a => {
    const card = a.closest('div[jsaction]') || a.parentElement;
    return {
        name: a.getAttribute('aria-label') || '',
        href: a.href || '',
        rating: card.querySelector('span.MW4etd')?.textContent || null,
        reviews: card.querySelector('span.UY7F9')?.textContent || null,
        website: card.querySelector('a[data-value="Website"]')?.href || null,
        text: card.innerText || ''
    };
})
"""


def search(query: str, state: str) -> list[Business]:
    """Busca en Google Maps y devuelve la lista de Business (interfaz síncrona)."""
    source_query = build_text_query(query, state)
    try:
        raw_cards = asyncio.run(_search_async(source_query))
    except Exception:
        logger.exception(f"Google Maps falló para '{source_query}'")
        return []

    businesses: list[Business] = []
    seen: set[str] = set()
    for card in raw_cards:
        business = _to_business(card, source_query, state)
        if business and business.place_id not in seen:
            seen.add(business.place_id)
            businesses.append(business)

    logger.info(f"Google Maps: '{source_query}' -> {len(businesses)} negocios")
    return businesses


async def _search_async(source_query: str) -> list[dict[str, Any]]:
    """Abre Maps, hace scroll del feed y devuelve las tarjetas crudas."""
    url = MAPS_SEARCH_URL.format(quote_plus(source_query))

    async with PlaywrightManager() as manager:
        async with manager.page() as page:
            # hasta 2 intentos: los errores de red transitorios son comunes
            for attempt in (1, 2):
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                    break
                except PlaywrightError:
                    if attempt == 2:
                        raise
                    logger.debug(f"goto falló para '{source_query}', reintentando")
                    await page.wait_for_timeout(3000)
            await _dismiss_consent(page)

            feed = page.locator('div[role="feed"]')
            try:
                await feed.wait_for(state="visible", timeout=15000)
            except TimeoutError:
                logger.warning(f"Sin panel de resultados para '{source_query}'")
                return []

            for _ in range(MAX_SCROLLS):
                count = await page.locator("a.hfpxzc").count()
                if count >= MAX_RESULTS:
                    break
                await feed.evaluate("el => el.scrollBy(0, 3000)")
                await page.wait_for_timeout(SCROLL_PAUSE_MS)
                feed_text = await feed.inner_text()
                if "end of the list" in feed_text.lower():
                    break

            return await page.evaluate(EXTRACT_JS)


async def _dismiss_consent(page) -> None:
    """Cierra el diálogo de consentimiento de Google si aparece."""
    try:
        button = page.locator(
            'button:has-text("Accept all"), button:has-text("Aceptar todo")'
        ).first
        await button.click(timeout=3000)
    except (TimeoutError, PlaywrightError):
        pass


def _to_business(
    card: dict[str, Any], source_query: str, state: str
) -> Business | None:
    """Convierte una tarjeta cruda de Maps en un Business."""
    name = (card.get("name") or "").strip()
    href = card.get("href") or ""
    if not name:
        return None

    address, phone = _parse_card_text(card.get("text") or "", name)

    return Business(
        place_id=_stable_id(href, name, address),
        business_name=name,
        source_query=source_query,
        google_maps_url=href or None,
        address=address,
        state=state,
        country="USA",
        phone=phone,
        website=card.get("website"),
        rating=_parse_rating(card.get("rating")),
        reviews=_parse_reviews(card.get("reviews")),
        scraped=False,
        status=Status.PENDING,
    )


def _stable_id(href: str, name: str, address: str | None) -> str:
    """place_id real si está en el link; si no, id estable derivado."""
    match = CHIJ_PATTERN.search(href)
    if match:
        return match.group(1)
    match = HEX_PATTERN.search(href)
    if match:
        return f"maps:{match.group(1)}"
    digest = hashlib.md5(f"{name}|{address or ''}".encode()).hexdigest()
    return f"maps:{digest}"


def _parse_card_text(text: str, name: str) -> tuple[str | None, str | None]:
    """Extrae dirección y teléfono del texto de la tarjeta.

    El texto viene en líneas tipo:
        Nombre / 4.8 (120) / Batting cage center · 123 Main St / Open ...
    """
    address = None
    phone_match = PHONE_PATTERN.search(text)
    phone = phone_match.group(0) if phone_match else None

    for line in text.split("\n"):
        line = line.strip()
        if "·" in line:
            candidate = line.split("·")[-1].strip()
            # una dirección suele empezar con número de calle
            if candidate and candidate[0].isdigit():
                address = candidate
                break
    return address, phone


def _parse_rating(value: str | None) -> float | None:
    try:
        return float(value.replace(",", ".")) if value else None
    except ValueError:
        return None


def _parse_reviews(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None
