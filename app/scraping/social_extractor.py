"""Extracción de redes sociales (Facebook, Instagram, TikTok, YouTube).

Recibe los links de un sitio y devuelve el mejor perfil por red,
descartando links de compartir, plugins y posts individuales.
"""

from urllib.parse import urlparse

# Rutas que no son perfiles: compartir, plugins, posts, login...
JUNK_PATH_FRAGMENTS = (
    "/sharer",
    "/share",
    "/plugins",
    "/intent",
    "/login",
    "/signup",
    "/watch",
    "/embed",
    "/reel",
    "/stories",
    "/hashtag",
    "/policies",
    "/legal",
)

# Basura específica por red (en Facebook "/p/" es un perfil válido,
# en Instagram es un post individual)
NETWORK_JUNK: dict[str, tuple[str, ...]] = {
    "instagram": ("/p/",),
    "facebook": ("/photo", "/events", "/groups/feed"),
    "youtube": ("/shorts",),
    "tiktok": ("/video/",),
}

SOCIAL_DOMAINS = {
    "facebook": ("facebook.com", "fb.com"),
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "youtube": ("youtube.com", "youtu.be"),
}


def extract_socials(links: set[str] | list[str]) -> dict[str, str | None]:
    """Devuelve {'facebook': url|None, 'instagram': ..., 'tiktok': ..., 'youtube': ...}."""
    result: dict[str, str | None] = {
        network: None for network in SOCIAL_DOMAINS
    }

    for link in links:
        parsed = urlparse(link)
        domain = parsed.netloc.lower()
        path = parsed.path.rstrip("/")

        for network, domains in SOCIAL_DOMAINS.items():
            if result[network] is not None:
                continue
            # Acepta el dominio y cualquier subdominio (www., web., m., es-la.)
            if not any(
                domain == d or domain.endswith("." + d) for d in domains
            ):
                continue
            if not path or _is_junk_path(path, network):
                continue
            result[network] = _clean(link)

    return result


def _is_junk_path(path: str, network: str) -> bool:
    lower = path.lower()
    if any(fragment in lower for fragment in JUNK_PATH_FRAGMENTS):
        return True
    return any(
        fragment in lower for fragment in NETWORK_JUNK.get(network, ())
    )


def _clean(url: str) -> str:
    """Quita query params y fragmentos: el perfil queda limpio."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
