"""Extracción de emails desde HTML.

Filtra falsos positivos típicos (nombres de archivo, dominios de ejemplo,
emails de plataformas) y devuelve los emails únicos en orden de aparición.
"""

import re

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.ASCII
)

# Dominios/fragmentos que casi siempre son basura, no contactos reales
JUNK_FRAGMENTS = (
    "example.com",
    "domain.com",
    "yourdomain",
    "email.com",
    "wixpress.com",
    "sentry.io",
    "sentry-next.wixpress",
    "godaddy.com",
    "placeholder",
    "no-reply",
    "noreply",
    "@2x",
)

# Extensiones de archivo que aparecen pegadas a un @ en srcsets/paths
FILE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")

# Prefijos de email genéricos ordenados por prioridad de contacto
PREFERRED_PREFIXES = ("info", "contact", "hello", "admin", "office", "sales")


def extract_emails(html: str) -> list[str]:
    """Devuelve los emails únicos y válidos encontrados, en orden."""
    found: list[str] = []
    seen: set[str] = set()
    for match in EMAIL_PATTERN.findall(html):
        email = match.strip().strip(".").lower()
        if email in seen or not _is_valid(email):
            continue
        seen.add(email)
        found.append(email)
    return found


def pick_best_email(emails: list[str]) -> str | None:
    """Elige el email más útil como contacto de negocio.

    Prioridad: prefijos típicos de contacto (info@, contact@...);
    si no hay, el primero encontrado.
    """
    if not emails:
        return None
    for prefix in PREFERRED_PREFIXES:
        for email in emails:
            if email.startswith(prefix + "@"):
                return email
    return emails[0]


def _is_valid(email: str) -> bool:
    if len(email) > 100:
        return False
    if any(fragment in email for fragment in JUNK_FRAGMENTS):
        return False
    if email.endswith(FILE_EXTENSIONS):
        return False
    local, _, domain = email.partition("@")
    if not local or "." not in domain:
        return False
    return True
