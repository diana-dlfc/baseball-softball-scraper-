"""Extracción heurística del nombre del dueño/fundador desde el texto.

Busca patrones como "Owner: John Smith", "John Smith, Founder",
"founded by John Smith". Es una heurística: cuando integremos la IA,
podrá complementar o validar este dato.
"""

import re

# Nombre propio: 2-3 palabras capitalizadas
NAME = r"([A-Z][a-zA-Z'\-]+(?:\s[A-Z][a-zA-Z'\-]+){1,2})"

TITLES = r"(?:owner|founder|co-founder|head\s+coach|director|president)"

# Descriptores que pueden aparecer entre "founded by" y el nombre:
# "founded by former MLB pitcher John Smith"
DESCRIPTOR = r"(?:(?:[a-z]+|[A-Z]{2,5})\s+){0,4}"

PATTERNS = [
    # "Owner: John Smith" / "Founder - John Smith"
    re.compile(TITLES + r"\s*[:\-–,]\s*" + NAME, re.IGNORECASE),
    # "John Smith, Owner" / "John Smith - Head Coach"
    re.compile(NAME + r"\s*[,\-–]\s*" + TITLES, re.IGNORECASE),
    # "founded by John Smith" / "Founded by former MLB pitcher John Smith"
    re.compile(
        r"(?:[Ff]ounded|[Oo]wned|[Ee]stablished)\s+[Bb]y\s+"
        + DESCRIPTOR + NAME
    ),
]

# Palabras que delatan un falso positivo en el "nombre" capturado
JUNK_WORDS = {
    "baseball", "softball", "academy", "training", "facility", "center",
    "the", "our", "your", "click", "here", "more", "read", "learn",
    "contact", "about", "team", "staff", "home", "page",
    "former", "professional", "pro", "mlb", "milb", "ncaa", "college",
    "pitcher", "catcher", "player", "league", "major", "minor",
}

HTML_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")


def extract_owner(html: str) -> str | None:
    """Devuelve el nombre del dueño/fundador más probable, o None."""
    text = WHITESPACE.sub(" ", HTML_TAG.sub(" ", html))

    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            if _looks_like_name(name):
                return name
    return None


def _looks_like_name(candidate: str) -> bool:
    words = candidate.lower().split()
    if not 2 <= len(words) <= 3:
        return False
    return not any(word in JUNK_WORDS for word in words)
