"""
Factory + singleton per i repository.

Legge la flag `data_source.repositories.piano` da config.json e istanzia
la concrezione appropriata (pandas o sql). Il singleton viene cachato
per evitare re-istanziazioni a ogni chiamata dei tool.

Reset del cache: `reset_repository_cache()` (utile nei test per swap).
"""

from typing import Optional
from data_sources.repositories.base import (
    PianoRepository,
    ControlliRepository,
    DiffRepository,
    RiskRepository,
    OsaRepository,
)


_piano_repo_cache: Optional[PianoRepository] = None
_controlli_repo_cache: Optional[ControlliRepository] = None
_diff_repo_cache: Optional[DiffRepository] = None
_risk_repo_cache: Optional[RiskRepository] = None
_osa_repo_cache: Optional[OsaRepository] = None


def _get_repo_mode(name: str, default: str = "pandas") -> str:
    """
    Legge `data_source.repositories.<name>` da config.json.

    Returns:
        "pandas" (default) o "sql"
    """
    try:
        from configs.config_loader import get_config
        cfg = get_config().config  # type: ignore[attr-defined]
        mode = (
            cfg.get("data_source", {})
            .get("repositories", {})
            .get(name, default)
        )
        return str(mode).lower()
    except Exception:
        return default


def get_piano_repository(force: Optional[str] = None) -> PianoRepository:
    """
    Ritorna l'istanza corrente del PianoRepository.

    Args:
        force: Se specificato ("pandas" o "sql"), istanzia senza cache.
            Usato nei contract test per parametrizzare.

    Returns:
        Istanza di PianoRepository (concrezione determinata da config flag
        `data_source.repositories.piano`).
    """
    global _piano_repo_cache

    mode = force.lower() if force else _get_repo_mode("piano")

    if force is None and _piano_repo_cache is not None:
        return _piano_repo_cache

    if mode == "sql":
        from data_sources.repositories.sql_piano_repository import SqlPianoRepository
        repo: PianoRepository = SqlPianoRepository()
    else:
        from data_sources.repositories.pandas_piano_repository import PandasPianoRepository
        repo = PandasPianoRepository()

    if force is None:
        _piano_repo_cache = repo

    return repo


def get_controlli_repository(force: Optional[str] = None) -> ControlliRepository:
    """
    Ritorna l'istanza corrente del ControlliRepository.

    Flag: data_source.repositories.controlli (default "pandas").
    """
    global _controlli_repo_cache

    mode = force.lower() if force else _get_repo_mode("controlli")

    if force is None and _controlli_repo_cache is not None:
        return _controlli_repo_cache

    if mode == "sql":
        from data_sources.repositories.sql_controlli_repository import SqlControlliRepository
        repo: ControlliRepository = SqlControlliRepository()
    else:
        from data_sources.repositories.pandas_controlli_repository import PandasControlliRepository
        repo = PandasControlliRepository()

    if force is None:
        _controlli_repo_cache = repo

    return repo


def get_diff_repository(force: Optional[str] = None) -> DiffRepository:
    """
    Ritorna l'istanza corrente del DiffRepository.

    Flag: data_source.repositories.diff (default "pandas").
    """
    global _diff_repo_cache

    mode = force.lower() if force else _get_repo_mode("diff")

    if force is None and _diff_repo_cache is not None:
        return _diff_repo_cache

    if mode == "sql":
        from data_sources.repositories.sql_diff_repository import SqlDiffRepository
        repo: DiffRepository = SqlDiffRepository()
    else:
        from data_sources.repositories.pandas_diff_repository import PandasDiffRepository
        repo = PandasDiffRepository()

    if force is None:
        _diff_repo_cache = repo

    return repo


def get_risk_repository(force: Optional[str] = None) -> RiskRepository:
    """
    Ritorna l'istanza corrente del RiskRepository.

    Flag: data_source.repositories.risk (default "pandas").

    La variante SQL legge da `v_risk_score_per_attivita` (view esistente),
    la variante pandas delega al calcolo legacy di RiskAnalyzer.
    """
    global _risk_repo_cache

    mode = force.lower() if force else _get_repo_mode("risk")

    if force is None and _risk_repo_cache is not None:
        return _risk_repo_cache

    if mode == "sql":
        from data_sources.repositories.sql_risk_repository import SqlRiskRepository
        repo: RiskRepository = SqlRiskRepository()
    else:
        from data_sources.repositories.pandas_risk_repository import PandasRiskRepository
        repo = PandasRiskRepository()

    if force is None:
        _risk_repo_cache = repo

    return repo


def get_osa_repository(force: Optional[str] = None) -> OsaRepository:
    """
    Ritorna l'istanza corrente del OsaRepository.
    Flag: data_source.repositories.osa (default "pandas").
    """
    global _osa_repo_cache

    mode = force.lower() if force else _get_repo_mode("osa")

    if force is None and _osa_repo_cache is not None:
        return _osa_repo_cache

    if mode == "sql":
        from data_sources.repositories.sql_osa_repository import SqlOsaRepository
        repo: OsaRepository = SqlOsaRepository()
    else:
        from data_sources.repositories.pandas_osa_repository import PandasOsaRepository
        repo = PandasOsaRepository()

    if force is None:
        _osa_repo_cache = repo

    return repo


def reset_repository_cache() -> None:
    """Svuota il cache dei singleton. Usato nei test per swap impl."""
    global _piano_repo_cache, _controlli_repo_cache, _diff_repo_cache, _risk_repo_cache, _osa_repo_cache
    _piano_repo_cache = None
    _controlli_repo_cache = None
    _diff_repo_cache = None
    _risk_repo_cache = None
    _osa_repo_cache = None
