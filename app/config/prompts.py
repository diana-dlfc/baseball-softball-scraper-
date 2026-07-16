"""Prompts para el clasificador IA."""

from app.database.models import Business

# Categorías finales del directorio
FINAL_CATEGORIES = [
    "Academy",
    "Training Facility",
    "Batting Cages",
    "Instructor",
    "Sports Complex",
    "Club",
    "Other",
]

CLASSIFIER_SYSTEM_PROMPT = """\
You are a precise data classifier for a directory of private baseball and \
softball training businesses in the USA. You always respond with a single \
valid JSON object and nothing else: no markdown, no code fences, no comments.\
"""

CLASSIFIER_USER_TEMPLATE = """\
Classify this business:

Name: {name}
Google category: {google_category}
Found via search: {source_query}
Address: {address}
Website: {website}

Respond with exactly this JSON structure:
{{
  "relevant": <true if this is a private baseball/softball training business \
(academy, training facility, batting cages, private instructor, travel club \
with training); false if it is a public park, school team, city league, \
retail store, stadium, or unrelated business. IMPORTANT: generic unnamed \
locations like "Softball field", "Baseball field" or "Baseball diamond" are \
public fields, NOT businesses -> always false>,
  "category": <one of: {categories}>,
  "indoor": <true/false/null if unknown>,
  "outdoor": <true/false/null if unknown>,
  "baseball": <true if it serves baseball players>,
  "softball": <true if it serves softball players>
}}\
"""


def build_classifier_prompt(business: Business) -> str:
    """Construye el prompt de usuario para clasificar un negocio."""
    return CLASSIFIER_USER_TEMPLATE.format(
        name=business.business_name,
        google_category=business.google_category or "unknown",
        source_query=business.source_query or "unknown",
        address=business.address or "unknown",
        website=business.website or "none",
        categories=", ".join(f'"{c}"' for c in FINAL_CATEGORIES),
    )
