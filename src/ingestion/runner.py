"""Orquestra a ingestão das fontes com cache idempotente na camada bronze."""

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import polars as pl

from config.settings import Settings
from ingestion import sources
from ingestion.client import CamaraClient
from storage.bronze import BronzeStore

logger = logging.getLogger(__name__)

SOURCE_ORDER: tuple[str, ...] = (
    "deputies",
    "propositions",
    "authors",
    "votings",
    "votes",
    "speeches",
)


def build_labels(settings: Settings) -> dict[str, str]:
    """Deriva o rótulo de cache de cada fonte a partir dos parâmetros de ingestão.

    Parameters
    ----------
    settings : Settings
        Configuração validada.

    Returns
    -------
    dict[str, str]
        Mapa ``fonte -> rótulo``.

    Examples
    --------
    >>> build_labels(settings)["deputies"]
    'legislatura-57'
    """
    cfg = settings.ingestion
    period = f"{cfg.start_date.isoformat()}_{cfg.end_date.isoformat()}"
    types = "-".join(cfg.proposition_types)
    return {
        "deputies": f"legislatura-{cfg.legislature_id}",
        "propositions": f"{period}_{types}",
        "authors": f"{period}_{types}",
        "votings": period,
        "votes": period,
        "speeches": f"legislatura-{cfg.legislature_id}_{period}",
    }


def _records_to_frame(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """Converte registros em DataFrame, inferindo o schema com todas as linhas."""
    if not rows:
        return pl.DataFrame()
    return pl.from_dicts(rows, infer_schema_length=None)


def _ingest_source(
    store: BronzeStore,
    source: str,
    label: str,
    params: dict[str, Any],
    fetch: Callable[[], list[dict[str, Any]]],
    refresh: bool,
) -> Path:
    """Executa a ingestão de uma fonte, pulando-a se já houver snapshot em cache."""
    cached = store.latest_snapshot(source, label)
    if cached is not None and not refresh:
        logger.info("Cache bronze encontrado para %s: %s", source, cached.name)
        return cached
    logger.info("Ingerindo %s (%s)", source, label)
    return store.write_snapshot(_records_to_frame(fetch()), source, label, params)


def run_ingestion(
    settings: Settings,
    selected: Sequence[str] = SOURCE_ORDER,
    refresh: bool = False,
    client: CamaraClient | None = None,
) -> dict[str, Path]:
    """Ingere as fontes selecionadas para a camada bronze, de forma idempotente.

    Fontes dependentes leem snapshots bronze anteriores: ``authors`` usa
    ``propositions``, ``votes`` usa ``votings`` e ``speeches`` usa ``deputies``.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    selected : Sequence[str], optional
        Subconjunto de ``SOURCE_ORDER``; by default todas.
    refresh : bool, optional
        Se ``True``, ignora o cache e grava um novo snapshot datado, by default False.
    client : CamaraClient, optional
        Cliente já configurado (injetável em testes).

    Returns
    -------
    dict[str, Path]
        Snapshot bronze de cada fonte processada.

    Raises
    ------
    ValueError
        Se alguma fonte selecionada for desconhecida.
    IngestionError
        Se a API falhar definitivamente ou não retornar registros.
    DataNotFoundError
        Se uma fonte dependente for pedida sem seu pré-requisito ingerido.

    Examples
    --------
    >>> run_ingestion(settings, selected=["deputies"])
    """
    unknown = set(selected) - set(SOURCE_ORDER)
    if unknown:
        raise ValueError(f"Fontes desconhecidas: {sorted(unknown)}")

    cfg = settings.ingestion
    labels = build_labels(settings)
    store = BronzeStore(settings.paths.bronze)
    owns_client = client is None
    http = client or CamaraClient(cfg)
    results: dict[str, Path] = {}

    try:
        for source in (name for name in SOURCE_ORDER if name in selected):
            label = labels[source]
            params = {"label": label, **cfg.model_dump(mode="json", exclude={"user_agent"})}

            def fetch(name: str = source) -> list[dict[str, Any]]:
                """Despacha a consulta da fonte ``name``."""
                return _dispatch(name, http, store, labels, settings)

            results[source] = _ingest_source(store, source, label, params, fetch, refresh)
    finally:
        if owns_client:
            http.close()
    return results


def _dispatch(
    source: str,
    client: CamaraClient,
    store: BronzeStore,
    labels: dict[str, str],
    settings: Settings,
) -> list[dict[str, Any]]:
    """Chama a função ``fetch_*`` adequada, lendo dependências da bronze quando necessário."""
    cfg = settings.ingestion
    if source == "deputies":
        return sources.fetch_deputies(client, cfg.legislature_id)
    if source == "propositions":
        return sources.fetch_propositions(
            client, cfg.proposition_types, cfg.start_date, cfg.end_date
        )
    if source == "authors":
        ids = store.read_latest("propositions", labels["propositions"])["id"].unique().to_list()
        return sources.fetch_authors(client, ids, cfg.max_workers)
    if source == "votings":
        return sources.fetch_votings(client, cfg.start_date, cfg.end_date)
    if source == "votes":
        ids = store.read_latest("votings", labels["votings"])["id"].unique().to_list()
        return sources.fetch_votes(client, ids, cfg.max_workers)
    ids = store.read_latest("deputies", labels["deputies"])["id"].unique().to_list()
    return sources.fetch_speeches(client, ids, cfg.start_date, cfg.end_date, cfg.max_workers)
