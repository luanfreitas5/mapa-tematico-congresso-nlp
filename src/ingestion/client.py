"""Cliente HTTP da API de Dados Abertos da Câmara (paginação + retry)."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from itertools import chain
from types import TracebackType
from typing import Any

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import IngestionConfig
from exceptions.data import IngestionError, ResourceNotFoundError

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class _RetryableHttpError(Exception):
    """Resposta HTTP transitória (429/5xx) que justifica nova tentativa."""


class CamaraClient:
    """Cliente da API v2 com tentativas automáticas e paginação.

    Parameters
    ----------
    config : IngestionConfig
        Parâmetros de ingestão (URL base, timeout, retries etc.).
    transport : httpx.BaseTransport, optional
        Transporte customizado; útil para testes com ``httpx.MockTransport``.

    Examples
    --------
    >>> with CamaraClient(settings.ingestion) as client:
    ...     rows = client.get_all("/deputados", {"idLegislatura": 57})
    """

    def __init__(
        self, config: IngestionConfig, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._config = config
        self._http = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": config.user_agent},
            transport=transport,
        )

    def __enter__(self) -> CamaraClient:
        """Entra no contexto, devolvendo o próprio cliente."""
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        """Fecha a conexão HTTP ao sair do contexto."""
        self.close()

    def close(self) -> None:
        """Fecha a conexão HTTP subjacente."""
        self._http.close()

    def get_json(self, path_or_url: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Executa um GET com retry exponencial e devolve o JSON.

        Parameters
        ----------
        path_or_url : str
            Caminho relativo à URL base (ex.: ``/deputados``) ou URL completa
            (usada para seguir o link ``next`` da paginação).
        params : Mapping[str, Any], optional
            Parâmetros de consulta.

        Returns
        -------
        dict[str, Any]
            Corpo da resposta decodificado.

        Raises
        ------
        ResourceNotFoundError
            Para HTTP 404 (subclasse de ``IngestionError``; sem retry).
        IngestionError
            Para demais erros 4xx não transitórios ou após esgotar as tentativas.
        """
        retrying = Retrying(
            retry=retry_if_exception_type((httpx.TransportError, _RetryableHttpError)),
            stop=stop_after_attempt(self._config.max_retries),
            wait=wait_exponential(multiplier=self._config.backoff_seconds, max=60),
            reraise=True,
        )
        try:
            return retrying(self._request_once, path_or_url, params)
        except (httpx.TransportError, _RetryableHttpError) as exc:
            raise IngestionError(
                f"Falha ao consultar {path_or_url} após "
                f"{self._config.max_retries} tentativas: {exc}"
            ) from exc

    def _request_once(self, path_or_url: str, params: Mapping[str, Any] | None) -> dict[str, Any]:
        """Faz uma única requisição, classificando falhas como transitórias ou definitivas."""
        response = self._http.get(path_or_url, params=params)
        if response.status_code in _RETRYABLE_STATUS:
            logger.warning("HTTP %s em %s; nova tentativa", response.status_code, path_or_url)
            raise _RetryableHttpError(f"HTTP {response.status_code}")
        if response.status_code == 404:
            raise ResourceNotFoundError(f"HTTP 404 em {path_or_url}")
        if response.status_code >= 400:
            raise IngestionError(f"HTTP {response.status_code} em {path_or_url}")
        return response.json()

    def iter_pages(
        self, path: str, params: Mapping[str, Any] | None = None, paginated: bool = True
    ) -> Iterator[list[dict[str, Any]]]:
        """Itera as páginas de um endpoint, seguindo ``links[rel=next]``.

        Parameters
        ----------
        path : str
            Caminho do endpoint.
        params : Mapping[str, Any], optional
            Parâmetros de consulta; ``itens`` é preenchido com ``page_size``.
        paginated : bool, optional
            Se ``False``, não envia ``itens``. Necessário em endpoints sem paginação
            (ex.: ``/proposicoes/{id}/autores`` e ``/votacoes/{id}/votos``), que
            respondem HTTP 400 a esse parâmetro, by default True.

        Yields
        ------
        list[dict[str, Any]]
            Registros (``dados``) de cada página.
        """
        base: dict[str, Any] = {"itens": self._config.page_size} if paginated else {}
        query: dict[str, Any] = {**base, **(params or {})}
        payload = self.get_json(path, query)
        while True:
            yield payload.get("dados", [])
            next_url = next(
                (link["href"] for link in payload.get("links", []) if link.get("rel") == "next"),
                None,
            )
            if not next_url:
                return
            payload = self.get_json(next_url)

    def get_all(
        self, path: str, params: Mapping[str, Any] | None = None, paginated: bool = True
    ) -> list[dict[str, Any]]:
        """Reúne todas as páginas de um endpoint em uma única lista.

        Parameters
        ----------
        path : str
            Caminho do endpoint.
        params : Mapping[str, Any], optional
            Parâmetros de consulta.
        paginated : bool, optional
            Se ``False``, não envia ``itens`` (ver ``iter_pages``), by default True.

        Returns
        -------
        list[dict[str, Any]]
            Todos os registros.
        """
        return list(chain.from_iterable(self.iter_pages(path, params, paginated)))
