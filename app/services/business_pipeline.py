"""Pipeline principal de la fase Google Places -> Supabase.

Recorre las combinaciones estado x búsqueda, delega cada búsqueda en
places_search.search_and_save y acumula estadísticas globales.

Preparado para checkpoints/resume: cada búsqueda es una SearchTask con un
id determinístico, y el avance se consulta/registra a través de la interfaz
Checkpoint. Hoy se usa NoCheckpoint (no persiste nada); en el futuro bastará
con implementar esa interfaz sobre un archivo o una tabla de Supabase,
sin tocar el bucle principal.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol

from app.config.search_queries import SEARCH_QUERIES
from app.config.settings import SEARCH_DELAY
from app.config.states import STATES
from app.google.places_client import QuotaExceededError
from app.google.places_search import search_and_save
from app.search.search_engine import SearchEngine
from app.utils.logger import (
    logger,
    log_scraper_start,
    log_scraper_end,
    _format_elapsed,
)


# ---------------------------------------------------------------------------
# Tareas y checkpoints
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SearchTask:
    """Una búsqueda individual del pipeline: (estado, consulta)."""

    state: str
    query: str

    @property
    def id(self) -> str:
        """Identificador determinístico, estable entre ejecuciones."""
        return f"{self.state}|{self.query}"


class Checkpoint(Protocol):
    """Interfaz de checkpoints. Implementarla permitirá el resume futuro."""

    def is_completed(self, task_id: str) -> bool: ...

    def mark_completed(self, task_id: str) -> None: ...


class NoCheckpoint:
    """Implementación nula: no persiste nada, nunca omite tareas."""

    def is_completed(self, task_id: str) -> bool:
        return False

    def mark_completed(self, task_id: str) -> None:
        pass


class FileCheckpoint:
    """Checkpoint persistente en un archivo JSON.

    Guarda los ids de las tareas completadas; al re-ejecutar el pipeline,
    las tareas ya hechas se omiten y el proceso continúa donde quedó.
    """

    DEFAULT_PATH = Path("output/checkpoint.json")

    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        self.path = Path(path)
        self._completed: set[str] = set()
        if self.path.exists():
            try:
                self._completed = set(
                    json.loads(self.path.read_text(encoding="utf-8"))
                )
                logger.info(
                    f"Checkpoint cargado: {len(self._completed)} búsquedas "
                    f"ya completadas ({self.path})"
                )
            except (json.JSONDecodeError, OSError):
                logger.warning(
                    f"Checkpoint ilegible en {self.path}; empezando desde cero"
                )

    def is_completed(self, task_id: str) -> bool:
        return task_id in self._completed

    def mark_completed(self, task_id: str) -> None:
        self._completed.add(task_id)
        self._save()

    def clear(self) -> None:
        """Borra el checkpoint (empezar desde cero)."""
        self._completed = set()
        self.path.unlink(missing_ok=True)
        logger.info("Checkpoint eliminado")

    def _save(self) -> None:
        """Escritura atómica: primero a .tmp, luego reemplaza."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(sorted(self._completed), ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)


def build_tasks(
    states: Iterable[str], queries: Iterable[str]
) -> list[SearchTask]:
    """Genera la lista ordenada y determinística de tareas del pipeline."""
    return [SearchTask(state, query) for state in states for query in queries]


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------

@dataclass
class PipelineStats:
    """Acumulador de estadísticas de una ejecución del pipeline."""

    total_tasks: int = 0
    completed: int = 0
    skipped: int = 0
    errors: int = 0
    found: int = 0
    inserted: int = 0
    updated: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_at

    @property
    def eta_seconds(self) -> float | None:
        """Tiempo estimado restante según el promedio por tarea ejecutada."""
        executed = self.completed + self.errors
        if executed == 0:
            return None
        remaining = self.total_tasks - self.skipped - executed
        return (self.elapsed_seconds / executed) * remaining


# ---------------------------------------------------------------------------
# Bucle principal
# ---------------------------------------------------------------------------

def run_pipeline(
    states: Iterable[str] | None = None,
    queries: Iterable[str] | None = None,
    dry_run: bool = False,
    checkpoint: Checkpoint | None = None,
    delay: float = SEARCH_DELAY,
) -> PipelineStats:
    """Ejecuta la fase Google Places -> Supabase.

    Un fallo en una búsqueda se registra y el pipeline continúa.
    Devuelve las estadísticas completas de la ejecución.
    """
    states = list(states) if states is not None else STATES
    queries = list(queries) if queries is not None else SEARCH_QUERIES
    checkpoint = checkpoint or NoCheckpoint()
    engine = SearchEngine()  # un motor por ejecución: mantiene el fallback

    tasks = build_tasks(states, queries)
    stats = PipelineStats(total_tasks=len(tasks))

    log_scraper_start()
    logger.info(
        f"Pipeline: {len(states)} estados x {len(queries)} búsquedas "
        f"= {len(tasks)} tareas | dry_run={dry_run}"
    )

    for index, task in enumerate(tasks, start=1):
        if checkpoint.is_completed(task.id):
            stats.skipped += 1
            logger.debug(f"({index}/{len(tasks)}) Omitida (checkpoint): {task.id}")
            continue

        try:
            found, inserted, updated = search_and_save(
                task.query, task.state, dry_run=dry_run, engine=engine
            )
            stats.found += found
            stats.inserted += inserted
            stats.updated += updated
            stats.completed += 1
            checkpoint.mark_completed(task.id)
        except QuotaExceededError:
            stats.errors += 1
            logger.critical(
                f"({index}/{len(tasks)}) CUOTA DIARIA DE GOOGLE AGOTADA. "
                "Abortando pipeline. El checkpoint permite reanudar mañana "
                "con el mismo comando: las búsquedas completadas se omitirán."
            )
            break
        except Exception:
            stats.errors += 1
            logger.exception(f"({index}/{len(tasks)}) Búsqueda fallida: {task.id}")

        _log_progress(index, stats)

        if index < len(tasks):
            time.sleep(delay)

    _log_summary(stats, dry_run)
    return stats


def _log_progress(index: int, stats: PipelineStats) -> None:
    """Loggea progreso: contador, porcentaje, transcurrido y ETA."""
    percent = index / stats.total_tasks * 100
    eta = stats.eta_seconds
    eta_text = _format_elapsed(eta) if eta is not None else "calculando..."
    logger.info(
        f"Progreso: {index}/{stats.total_tasks} ({percent:.1f}%) | "
        f"transcurrido: {_format_elapsed(stats.elapsed_seconds)} | "
        f"ETA: {eta_text}"
    )


def _log_summary(stats: PipelineStats, dry_run: bool) -> None:
    """Resumen final de la ejecución."""
    logger.success("-" * 60)
    logger.success("RESUMEN DEL PIPELINE" + (" (DRY-RUN)" if dry_run else ""))
    logger.success(f"Búsquedas completadas : {stats.completed}/{stats.total_tasks}")
    logger.success(f"Omitidas (checkpoint) : {stats.skipped}")
    logger.success(f"Fallidas              : {stats.errors}")
    logger.success(f"Negocios encontrados  : {stats.found}")
    logger.success(f"Insertados en Supabase: {stats.inserted}")
    logger.success(f"Actualizados          : {stats.updated}")
    logger.success("-" * 60)
    log_scraper_end(stats.inserted + stats.updated, stats.elapsed_seconds)
