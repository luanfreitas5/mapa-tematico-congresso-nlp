"""Testes do cliente HTTP: paginação, retry e erros."""

import httpx
import pytest

from exceptions.data import IngestionError, ResourceNotFoundError
from ingestion.client import CamaraClient


def _client(tmp_settings, handler) -> CamaraClient:
    """Cria um cliente com transporte simulado."""
    return CamaraClient(tmp_settings.ingestion, transport=httpx.MockTransport(handler))


def test_pagination_follows_next_link(tmp_settings):
    """O cliente segue links[rel=next] até a última página."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("pagina") == "2":
            return httpx.Response(200, json={"dados": [{"id": 2}], "links": []})
        next_link = {"rel": "next", "href": "https://dadosabertos.camara.leg.br/api/v2/x?pagina=2"}
        return httpx.Response(200, json={"dados": [{"id": 1}], "links": [next_link]})

    with _client(tmp_settings, handler) as client:
        assert client.get_all("/x") == [{"id": 1}, {"id": 2}]


def test_unpaginated_request_omits_itens(tmp_settings):
    """Endpoints sem paginação (autores, votos) respondem 400 a ``itens``; o cliente não o envia."""
    seen: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append("itens" in request.url.params)
        if "itens" in request.url.params:
            return httpx.Response(400)
        return httpx.Response(200, json={"dados": [{"id": 1}], "links": []})

    with _client(tmp_settings, handler) as client:
        assert client.get_all("/x/autores", paginated=False) == [{"id": 1}]
        with pytest.raises(IngestionError):
            client.get_all("/x/autores")  # paginado envia itens e recebe o 400 simulado
    assert seen == [False, True]


def test_retries_transient_errors_then_succeeds(tmp_settings):
    """Erros 503 são repetidos até o sucesso."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"dados": [{"id": 1}], "links": []})

    with _client(tmp_settings, handler) as client:
        assert client.get_all("/x") == [{"id": 1}]
    assert attempts["n"] == 3


def test_gives_up_after_max_retries(tmp_settings):
    """Esgotadas as tentativas, levanta IngestionError."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(503)

    with _client(tmp_settings, handler) as client, pytest.raises(IngestionError):
        client.get_json("/x")
    assert attempts["n"] == tmp_settings.ingestion.max_retries


def test_client_error_is_not_retried(tmp_settings):
    """Erros 4xx (exceto 429) falham imediatamente."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(404)

    with _client(tmp_settings, handler) as client, pytest.raises(IngestionError):
        client.get_json("/x")
    assert attempts["n"] == 1


def test_transport_error_is_retried(tmp_settings):
    """Falhas de rede são repetidas e, se persistirem, viram IngestionError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=request)

    with _client(tmp_settings, handler) as client, pytest.raises(IngestionError):
        client.get_json("/x")


def test_404_raises_resource_not_found_without_retry(tmp_settings):
    """HTTP 404 vira ResourceNotFoundError (subclasse de IngestionError) sem nova tentativa."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(404)

    with _client(tmp_settings, handler) as client, pytest.raises(ResourceNotFoundError):
        client.get_all("/x/votos", paginated=False)
    assert attempts["n"] == 1
    assert issubclass(ResourceNotFoundError, IngestionError)
