"""Cliente LLM compatible con la API de OpenAI (NVIDIA NIM, Groq, etc.).

Usa el modelo principal (LLM_*) y, si falla, reintenta con el fallback
(LLM_FALLBACK_*) cuando está configurado en el .env.
"""

import itertools
import time

from openai import OpenAI, RateLimitError

from app.config.settings import (
    LLM_BASE_URL,
    LLM_DISABLE_THINKING,
    LLM_MAX_TOKENS,
    LLM_PROVIDERS,
    LLM_TEMPERATURE,
)
from app.utils.logger import logger


class LLMError(Exception):
    """Fallaron todos los proveedores LLM configurados."""


class LLMClient:
    """Cliente multi-proveedor con rotación (round-robin).

    Cada llamada alterna entre los proveedores configurados, sumando
    sus rate limits. Si uno falla, la llamada se reintenta con el otro.
    """

    def __init__(self) -> None:
        if not LLM_PROVIDERS:
            raise EnvironmentError(
                "No hay proveedores LLM configurados en el .env (LLM_API_KEY...)"
            )

        self._providers: list[tuple[OpenAI, str]] = [
            (OpenAI(api_key=key, base_url=url or LLM_BASE_URL), model)
            for key, url, model in LLM_PROVIDERS
        ]
        logger.info(
            f"LLM: {len(self._providers)} proveedor(es) en rotación: "
            + ", ".join(model for _, model in self._providers)
        )
        self._counter = itertools.count()
        # circuit breaker: proveedor en rate limit descansa COOLDOWN_SECONDS
        self._cooldown_until: list[float] = [0.0] * len(self._providers)

    COOLDOWN_SECONDS = 60

    def chat(self, system: str, user: str) -> str:
        """Envía un chat rotando entre proveedores. Lanza LLMError si todos fallan."""
        n = len(self._providers)
        start = next(self._counter) % n
        errors: list[str] = []
        now = time.time()

        for offset in range(n):
            index = (start + offset) % n
            client, model = self._providers[index]

            if now < self._cooldown_until[index]:
                errors.append(f"{model}: en cooldown")
                continue

            try:
                return self._request(client, model, system, user)
            except RateLimitError:
                # descanso: dejar de martillar a este proveedor un rato
                self._cooldown_until[index] = time.time() + self.COOLDOWN_SECONDS
                errors.append(f"{model}: RateLimitError (cooldown {self.COOLDOWN_SECONDS}s)")
                logger.debug(f"{model} en rate limit; cooldown {self.COOLDOWN_SECONDS}s")
            except Exception as exc:
                errors.append(f"{model}: {type(exc).__name__}")

        raise LLMError(f"Todos los proveedores fallaron: {' | '.join(errors)}")

    @staticmethod
    def _request(client: OpenAI, model: str, system: str, user: str) -> str:
        extra_body = {}
        if LLM_DISABLE_THINKING and "nvidia" in str(client.base_url):
            # Solo NVIDIA NIM: desactiva el modo razonamiento de los modelos
            # que lo soportan (DeepSeek, Step). Otros proveedores no lo usan.
            extra_body = {"chat_template_kwargs": {"thinking": False}}
        if "gpt-oss" in model:
            # gpt-oss razona por defecto y quema el límite de tokens/minuto;
            # esfuerzo bajo basta de sobra para clasificar
            extra_body["reasoning_effort"] = "low"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            extra_body=extra_body,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Respuesta vacía del LLM")
        return content.strip()


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Singleton del cliente LLM."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
