"""Scraping de un website de negocio.

Responsabilidad única: dado un URL, visitar el homepage y hasta
MAX_EXTRA_PAGES páginas internas relevantes (contact, about, staff...),
y devolver el HTML crudo y los links encontrados.

No extrae emails ni redes: eso es trabajo de los extractores.
"""

from dataclasses import dataclass, field
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError, Page, TimeoutError

from app.scraping.playwright_manager import PlaywrightManager
from app.utils.logger import logger

# Páginas internas que suelen contener datos de contacto/equipo
CONTACT_HINTS = ("contact", "about", "staff", "team", "coaches", "our-story")

MAX_EXTRA_PAGES = 2


@dataclass
class ScrapedSite:
    """Resultado del scraping de un sitio: HTML de sus páginas y links."""

    url: str
    pages_html: list[str] = field(default_factory=list)
    links: set[str] = field(default_factory=set)

    @property
    def full_html(self) -> str:
        """HTML combinado de todas las páginas visitadas."""
        return "\n".join(self.pages_html)


def normalize_url(url: str) -> str:
    """Asegura que el URL tenga esquema http(s)."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def scrape_website(
    manager: PlaywrightManager, url: str
) -> ScrapedSite | None:
    """Visita el sitio y devuelve su contenido, o None si no cargó."""
    url = normalize_url(url)
    site = ScrapedSite(url=url)

    async with manager.page() as page:
        html = await _fetch(page, url)
        if html is None:
            return None
        site.pages_html.append(html)
        site.links.update(await _collect_links(page))

        for extra_url in _pick_contact_pages(site.links, url):
            extra_html = await _fetch(page, extra_url)
            if extra_html:
                site.pages_html.append(extra_html)
                site.links.update(await _collect_links(page))

    return site


async def _fetch(page: Page, url: str) -> str | None:
    """Navega a un URL y devuelve el HTML, o None si falla."""
    try:
        await page.goto(url, wait_until="domcontentloaded")
        return await page.content()
    except (TimeoutError, PlaywrightError) as exc:
        logger.debug(f"No se pudo cargar {url}: {type(exc).__name__}")
        return None


async def _collect_links(page: Page) -> list[str]:
    try:
        # e.href en anchors SVG es un objeto (SVGAnimatedString), no texto
        return await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => typeof e.href === 'string' "
            "? e.href : (e.href && e.href.baseVal) || '')"
            ".filter(h => h)",
        )
    except PlaywrightError:
        return []


def _pick_contact_pages(links: set[str], base_url: str) -> list[str]:
    """Elige hasta MAX_EXTRA_PAGES links internos tipo contact/about."""
    base_domain = urlparse(base_url).netloc.removeprefix("www.")
    candidates: list[str] = []
    for link in links:
        parsed = urlparse(link)
        if parsed.netloc.removeprefix("www.") != base_domain:
            continue
        path = parsed.path.lower()
        if any(hint in path for hint in CONTACT_HINTS):
            if link not in candidates:
                candidates.append(link)
    return candidates[:MAX_EXTRA_PAGES]
