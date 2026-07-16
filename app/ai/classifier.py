"""Clasificador IA de negocios.

Dado un Business, pregunta al LLM y devuelve una ClassificationResult con:
relevancia, categoría final, indoor/outdoor y baseball/softball.
"""

import json
import re
from dataclasses import dataclass

from app.ai.openai_client import get_llm_client
from app.config.prompts import (
    CLASSIFIER_SYSTEM_PROMPT,
    FINAL_CATEGORIES,
    build_classifier_prompt,
)
from app.database.models import Business
from app.utils.logger import logger
from app.utils.retry import retry

# Por si el modelo envuelve el JSON en ```json ... ```
CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# Nombres genéricos que son campos públicos, no negocios.
# Se marcan Irrelevant sin gastar una llamada al LLM.
GENERIC_FIELD_PATTERN = re.compile(
    r"^(baseball|softball|little league)?\s*(field|fields|diamond|diamonds|ball\s?park)\s*(#?\d+)?$",
    re.IGNORECASE,
)


@dataclass
class ClassificationResult:
    relevant: bool
    category: str
    indoor: bool | None
    outdoor: bool | None
    baseball: bool
    softball: bool

    def to_update_dict(self) -> dict:
        """Campos listos para update_business en Supabase."""
        data = {
            "category": self.category if self.relevant else "Irrelevant",
            "baseball": self.baseball,
            "softball": self.softball,
        }
        if self.indoor is not None:
            data["indoor"] = self.indoor
        if self.outdoor is not None:
            data["outdoor"] = self.outdoor
        return data


def classify_business(business: Business) -> ClassificationResult | None:
    """Clasifica un negocio con el LLM. Devuelve None si no se pudo."""
    name = (business.business_name or "").strip()
    if GENERIC_FIELD_PATTERN.match(name):
        # campo público genérico: irrelevante sin gastar LLM
        return ClassificationResult(
            relevant=False, category="Other",
            indoor=None, outdoor=None, baseball=False, softball=False,
        )

    prompt = build_classifier_prompt(business)
    try:
        raw = _chat_with_retry(prompt)
        return _parse_response(raw)
    except Exception:
        logger.exception(f"Clasificación falló para '{business.business_name}'")
        return None


@retry(times=4, delay=15)
def _chat_with_retry(prompt: str) -> str:
    """Llamada al LLM con reintentos largos (rate limit por minuto)."""
    return get_llm_client().chat(CLASSIFIER_SYSTEM_PROMPT, prompt)


def _parse_response(raw: str) -> ClassificationResult:
    """Parsea y valida el JSON devuelto por el modelo."""
    cleaned = CODE_FENCE.sub("", raw).strip()
    data = json.loads(cleaned)

    category = str(data.get("category", "Other"))
    if category not in FINAL_CATEGORIES:
        category = "Other"

    return ClassificationResult(
        relevant=bool(data.get("relevant", False)),
        category=category,
        indoor=_to_optional_bool(data.get("indoor")),
        outdoor=_to_optional_bool(data.get("outdoor")),
        baseball=bool(data.get("baseball", False)),
        softball=bool(data.get("softball", False)),
    )


def _to_optional_bool(value) -> bool | None:
    if value is None:
        return None
    return bool(value)
