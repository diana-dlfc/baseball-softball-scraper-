"""Orquestador de extracción de contacto de un negocio.

Responsabilidad única: dado un website, coordinar el scraping
(website_scraper) y los extractores, y devolver un ContactInfo
con todo lo encontrado. No conoce Supabase ni el pipeline.
"""

from dataclasses import dataclass

from app.scraping.email_extractor import extract_emails, pick_best_email
from app.scraping.owner_extractor import extract_owner
from app.scraping.playwright_manager import PlaywrightManager
from app.scraping.social_extractor import extract_socials
from app.scraping.website_scraper import scrape_website
from app.utils.logger import logger


@dataclass
class ContactInfo:
    """Datos de contacto extraídos del website de un negocio."""

    email: str | None = None
    facebook: str | None = None
    instagram: str | None = None
    tiktok: str | None = None
    youtube: str | None = None
    owner: str | None = None
    pages_visited: int = 0

    @property
    def found_anything(self) -> bool:
        return any(
            (self.email, self.facebook, self.instagram,
             self.tiktok, self.youtube, self.owner)
        )


class WebsiteUnreachable(Exception):
    """El website no cargó (dominio muerto, timeout, bloqueo)."""


async def extract_contact_info(
    manager: PlaywrightManager, website: str
) -> ContactInfo:
    """Scrapea el website y devuelve los datos de contacto encontrados.

    Lanza WebsiteUnreachable si el sitio no carga, para que el caller
    pueda registrar el error en la base de datos.
    """
    site = await scrape_website(manager, website)
    if site is None:
        raise WebsiteUnreachable(f"No se pudo cargar {website}")

    html = site.full_html
    socials = extract_socials(site.links)

    info = ContactInfo(
        email=pick_best_email(extract_emails(html)),
        facebook=socials["facebook"],
        instagram=socials["instagram"],
        tiktok=socials["tiktok"],
        youtube=socials["youtube"],
        owner=extract_owner(html),
        pages_visited=len(site.pages_html),
    )

    logger.debug(
        f"{website} | páginas: {info.pages_visited} | "
        f"email: {info.email or '-'} | owner: {info.owner or '-'}"
    )
    return info
