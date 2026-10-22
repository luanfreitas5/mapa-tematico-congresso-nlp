"""Funções que consultam cada endpoint da API e devolvem registros planos."""

import json
import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

from exceptions.data import ResourceNotFoundError
from ingestion.client import CamaraClient
from utils.dates import generate_month_windows
from utils.progress import create_progress

logger = logging.getLogger(__name__)

Record = dict[str, Any]


def normalize_record(record: Record) -> Record:
    """Serializa valores aninhados (dict/list) como JSON para um schema Parquet estável.

    Parameters
    ----------
    record : Record
        Registro como devolvido pela API.

    Returns
    -------
    Record
        Registro apenas com valores escalares ou ``None``.

    Examples
    --------
    >>> normalize_record({"id": 1, "fase": {"titulo": "x"}})
    {'id': 1, 'fase': '{"titulo": "x"}'}
    """
    return {
        key: json.dumps(value, ensure_ascii=False) if isinstance(value, dict | list) else value
        for key, value in record.items()
    }


def map_parallel(
    func: Callable[[Any], list[Record]],
    items: Iterable[Any],
    max_workers: int,
    description: str,
) -> list[Record]:
    """Aplica ``func`` a cada item em paralelo, concatenando os registros devolvidos.

    Parameters
    ----------
    func : Callable[[Any], list[Record]]
        Função que consulta a API para um item.
    items : Iterable[Any]
        Itens (ex.: identificadores de proposições).
    max_workers : int
        Número máximo de threads.
    description : str
        Texto exibido na barra de progresso.

    Returns
    -------
    list[Record]
        Registros de todos os itens (ordem de conclusão não é garantida).

    Raises
    ------
    IngestionError
        Propagada se alguma consulta falhar definitivamente.
    """
    item_list = list(items)
    rows: list[Record] = []
    with create_progress() as progress, ThreadPoolExecutor(max_workers=max_workers) as pool:
        task = progress.add_task(description, total=len(item_list))
        futures = [pool.submit(func, item) for item in item_list]
        try:
            for future in as_completed(futures):
                rows.extend(future.result())
                progress.advance(task)
        except BaseException:
            # Sem cancelar, o shutdown do executor aguardaria todas as tarefas pendentes
            # antes de propagar o erro (parece travado).
            logger.exception("Falha em '%s'; cancelando consultas pendentes", description)
            pool.shutdown(wait=False, cancel_futures=True)
            raise
    return rows


def fetch_deputies(client: CamaraClient, legislature_id: int) -> list[Record]:
    """Busca os deputados de uma legislatura (``/deputados``).

    Parameters
    ----------
    client : CamaraClient
        Cliente HTTP.
    legislature_id : int
        Identificador da legislatura (ex.: 57).

    Returns
    -------
    list[Record]
        Um registro por deputado.
    """
    rows = client.get_all(
        "/deputados", {"idLegislatura": legislature_id, "ordenarPor": "id", "ordem": "ASC"}
    )
    return [normalize_record(row) for row in rows]


def fetch_propositions(
    client: CamaraClient, types: list[str], start: date, end: date
) -> list[Record]:
    """Busca proposições apresentadas no período, mês a mês e tipo a tipo (``/proposicoes``).

    A coluna ``window_start`` (primeiro dia do mês da consulta) identifica o mês de
    apresentação, pois a listagem não traz a data de apresentação.

    Parameters
    ----------
    client : CamaraClient
        Cliente HTTP.
    types : list[str]
        Siglas de tipo (ex.: ``["PL", "PEC"]``).
    start : date
        Início do período (inclusivo).
    end : date
        Fim do período (inclusivo).

    Returns
    -------
    list[Record]
        Um registro por proposição, com ``window_start``.
    """
    rows: list[Record] = []
    windows = generate_month_windows(start, end)
    with create_progress() as progress:
        task = progress.add_task("Proposições", total=len(windows) * len(types))
        for window_start, window_end in windows:
            for proposition_type in types:
                page_rows = client.get_all(
                    "/proposicoes",
                    {
                        "siglaTipo": proposition_type,
                        "dataApresentacaoInicio": window_start.isoformat(),
                        "dataApresentacaoFim": window_end.isoformat(),
                        "ordenarPor": "id",
                        "ordem": "ASC",
                    },
                )
                month = window_start.replace(day=1).isoformat()
                rows.extend({**normalize_record(row), "window_start": month} for row in page_rows)
                progress.advance(task)
    return rows


def fetch_authors(
    client: CamaraClient, proposition_ids: list[int], max_workers: int
) -> list[Record]:
    """Busca os autores de cada proposição (``/proposicoes/{id}/autores``).

    Parameters
    ----------
    client : CamaraClient
        Cliente HTTP.
    proposition_ids : list[int]
        Identificadores das proposições.
    max_workers : int
        Threads simultâneas.

    Returns
    -------
    list[Record]
        Um registro por autor, com ``idProposicao``.
    """

    def fetch_one(proposition_id: int) -> list[Record]:
        """Consulta os autores de uma proposição."""
        rows = client.get_all(f"/proposicoes/{proposition_id}/autores", paginated=False)
        return [{**normalize_record(row), "idProposicao": proposition_id} for row in rows]

    return map_parallel(fetch_one, proposition_ids, max_workers, "Autores")


def fetch_votings(client: CamaraClient, start: date, end: date) -> list[Record]:
    """Busca as votações do período, mês a mês (``/votacoes``).

    Parameters
    ----------
    client : CamaraClient
        Cliente HTTP.
    start : date
        Início do período (inclusivo).
    end : date
        Fim do período (inclusivo).

    Returns
    -------
    list[Record]
        Um registro por votação.
    """
    rows: list[Record] = []
    for window_start, window_end in generate_month_windows(start, end):
        page_rows = client.get_all(
            "/votacoes",
            {
                "dataInicio": window_start.isoformat(),
                "dataFim": window_end.isoformat(),
                "ordenarPor": "dataHoraRegistro",
                "ordem": "ASC",
            },
        )
        rows.extend(normalize_record(row) for row in page_rows)
    return rows


def fetch_votes(client: CamaraClient, voting_ids: list[str], max_workers: int) -> list[Record]:
    """Busca os votos nominais de cada votação (``/votacoes/{id}/votos``).

    Votações simbólicas não têm votos nominais e retornam lista vazia; o mesmo vale
    para votações que a API responde com HTTP 404 em ``/votos``.

    Parameters
    ----------
    client : CamaraClient
        Cliente HTTP.
    voting_ids : list[str]
        Identificadores das votações.
    max_workers : int
        Threads simultâneas.

    Returns
    -------
    list[Record]
        Um registro por voto: ``idVotacao``, ``tipoVoto``, ``idDeputado``,
        ``siglaPartido``, ``siglaUf``.
    """

    def fetch_one(voting_id: str) -> list[Record]:
        """Consulta e achata os votos de uma votação."""
        try:
            rows = client.get_all(f"/votacoes/{voting_id}/votos", paginated=False)
        except ResourceNotFoundError:
            logger.debug("Votação %s sem votos (HTTP 404)", voting_id)
            return []
        return [
            {
                "idVotacao": voting_id,
                "tipoVoto": row.get("tipoVoto"),
                "dataRegistroVoto": row.get("dataRegistroVoto"),
                "idDeputado": (row.get("deputado_") or {}).get("id"),
                "siglaPartido": (row.get("deputado_") or {}).get("siglaPartido"),
                "siglaUf": (row.get("deputado_") or {}).get("siglaUf"),
            }
            for row in rows
        ]

    return map_parallel(fetch_one, voting_ids, max_workers, "Votos")


def fetch_speeches(
    client: CamaraClient, deputy_ids: list[int], start: date, end: date, max_workers: int
) -> list[Record]:
    """Busca os discursos de cada deputado no período (``/deputados/{id}/discursos``).

    Parameters
    ----------
    client : CamaraClient
        Cliente HTTP.
    deputy_ids : list[int]
        Identificadores dos deputados.
    start : date
        Início do período (inclusivo).
    end : date
        Fim do período (inclusivo).
    max_workers : int
        Threads simultâneas.

    Returns
    -------
    list[Record]
        Um registro por discurso, com ``idDeputado``.
    """

    def fetch_one(deputy_id: int) -> list[Record]:
        """Consulta os discursos de um deputado."""
        rows = client.get_all(
            f"/deputados/{deputy_id}/discursos",
            {
                "dataInicio": start.isoformat(),
                "dataFim": end.isoformat(),
                "ordenarPor": "dataHoraInicio",
                "ordem": "ASC",
            },
        )
        return [{**normalize_record(row), "idDeputado": deputy_id} for row in rows]

    return map_parallel(fetch_one, deputy_ids, max_workers, "Discursos")
