"""Reintentos con backoff exponencial para operaciones de red."""

import functools
import time
from typing import Callable, TypeVar

from app.utils.logger import logger

T = TypeVar("T")


def retry(
    times: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorador: reintenta la función con espera exponencial.

        @retry(times=3, delay=2)
        def llamada_de_red(): ...

    Espera 2s, luego 4s, luego lanza la excepción original.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            wait = delay
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == times:
                        raise
                    logger.warning(
                        f"{func.__name__} falló "
                        f"(intento {attempt}/{times}): {type(exc).__name__}. "
                        f"Reintentando en {wait:.0f}s..."
                    )
                    time.sleep(wait)
                    wait *= backoff
            raise RuntimeError("unreachable")  # para el type checker

        return wrapper

    return decorator
