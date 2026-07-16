"""Constantes globales del proyecto."""


class Status:
    """Estados posibles de un negocio en el pipeline."""

    PENDING = "pending"
    SCRAPING = "scraping"
    COMPLETED = "completed"
    ERROR = "error"
