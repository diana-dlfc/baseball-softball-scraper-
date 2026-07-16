"""Diagnóstico de los proveedores LLM: prueba cada uno y muestra el error real.

Uso:

    python -m scripts.test_llm
"""

import time

from openai import OpenAI

from app.config.settings import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    LLM_FALLBACK_API_KEY, LLM_FALLBACK_BASE_URL, LLM_FALLBACK_MODEL,
)

PROVIDERS = [
    ("PRINCIPAL", LLM_API_KEY, LLM_BASE_URL, LLM_MODEL),
    ("FALLBACK", LLM_FALLBACK_API_KEY, LLM_FALLBACK_BASE_URL, LLM_FALLBACK_MODEL),
]

VARIANTS = [
    ("sin extras", {}),
    ("con reasoning_effort=low", {"extra_body": {"reasoning_effort": "low"}}),
    ("con thinking=false", {"extra_body": {"chat_template_kwargs": {"thinking": False}}}),
]


def main() -> None:
    for name, key, base_url, model in PROVIDERS:
        if not key or not model:
            print(f"\n=== {name}: no configurado, se omite ===")
            continue
        print(f"\n=== {name}: {model} @ {base_url} ===")
        client = OpenAI(api_key=key, base_url=base_url)

        for variant_name, extra in VARIANTS:
            start = time.perf_counter()
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Reply with only: OK"}],
                    max_tokens=500,
                    temperature=0,
                    **extra,
                )
                content = (response.choices[0].message.content or "").strip()
                elapsed = time.perf_counter() - start
                print(f"  [{variant_name}] OK en {elapsed:.1f}s -> '{content[:40]}'")
            except Exception as exc:
                elapsed = time.perf_counter() - start
                print(f"  [{variant_name}] FALLO en {elapsed:.1f}s -> "
                      f"{type(exc).__name__}: {str(exc)[:200]}")
            time.sleep(2)


if __name__ == "__main__":
    main()
