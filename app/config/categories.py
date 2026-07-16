"""Categorías de Google permitidas y palabras clave bloqueadas."""

ALLOWED_GOOGLE_CATEGORIES = [
    "Sports complex",
    "Sports school",
    "Training centre",
    "Baseball club",
    "Softball club",
    "Batting cage center",
]

# Negocios legítimos que el filtro atraparía por error.
# Si el nombre contiene alguna de estas frases, NUNCA se bloquea.
WHITELIST_KEYWORDS = [
    "bpb training",
    "hitting academy",
    "grand slam usa",
    "browning baseball",
    "batter's box",
    "batters box",
]

BLOCKED_KEYWORDS = [
    "park",
    "school",
    "high school",
    "middle school",
    "elementary",
    "college",
    "university",
    "stadium",
    "arena",
    "little league",
    "municipal",
    "city park",
    "county park",
    "public park",
    "community park",
    "recreation",
    "sports store",
    "sporting goods",
]
