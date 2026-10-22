"""Fixtures compartilhadas: configuração com caminhos temporários e API simulada."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import matplotlib
import pytest

from config.settings import PathsConfig, Settings, load_settings
from ingestion.client import CamaraClient

LONG_SPEECH = " ".join(["palavra"] * 40)


@pytest.fixture(scope="session", autouse=True)
def use_headless_matplotlib_backend() -> None:
    """Usa o backend sem janela, evitando depender de Tk no ambiente de testes."""
    matplotlib.use("Agg")


@pytest.fixture(scope="session")
def base_settings() -> Settings:
    """Configuração real do repositório (somente leitura)."""
    return load_settings()


@pytest.fixture
def tmp_settings(base_settings: Settings, tmp_path: Path) -> Settings:
    """Configuração com todos os diretórios em ``tmp_path`` e janela de ingestão curta."""
    paths = base_settings.paths.model_copy(
        update={name: tmp_path / name for name in PathsConfig.model_fields}
    )
    ingestion = base_settings.ingestion.model_copy(
        update={
            "start_date": date(2023, 2, 1),
            "end_date": date(2023, 2, 28),
            "proposition_types": ["PT"],
            "backoff_seconds": 0.0,
            "max_retries": 3,
            "max_workers": 2,
        }
    )
    return base_settings.model_copy(update={"paths": paths, "ingestion": ingestion})


def build_api_handler(calls: list[str]) -> Callable[[httpx.Request], httpx.Response]:
    """Cria um handler que simula os endpoints usados na ingestão e registra as chamadas."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Responde a cada endpoint com um registro mínimo e válido."""
        path = request.url.path.removeprefix("/api/v2")
        calls.append(path)
        payloads: dict[str, list[dict[str, object]]] = {
            "/deputados": [
                {
                    "id": 1,
                    "nome": "Ana Teste",
                    "siglaPartido": "AAA",
                    "siglaUf": "SP",
                    "idLegislatura": 57,
                    "email": "ana@example.org",
                }
            ],
            "/proposicoes": [
                {
                    "id": 10,
                    "siglaTipo": "PL",
                    "numero": 1,
                    "ano": 2023,
                    "ementa": "Dispõe sobre a saúde pública e a educação básica nas escolas",
                }
            ],
            "/proposicoes/10/autores": [
                {
                    "uri": "https://dadosabertos.camara.leg.br/api/v2/deputados/1",
                    "nome": "Ana Teste",
                    "tipo": "Deputado",
                    "ordemAssinatura": 1,
                }
            ],
            "/votacoes": [{"id": "V1", "data": "2023-02-10"}],
            "/votacoes/V1/votos": [
                {
                    "tipoVoto": "Sim",
                    "dataRegistroVoto": "2023-02-10T10:00:00",
                    "deputado_": {"id": 1, "siglaPartido": "AAA", "siglaUf": "SP"},
                }
            ],
            "/deputados/1/discursos": [
                {
                    "dataHoraInicio": "2023-02-10T10:00",
                    "sumario": "Discurso sobre saúde",
                    "transcricao": LONG_SPEECH,
                    "faseEvento": {"titulo": "Grande Expediente"},
                }
            ],
        }
        if path in payloads:
            return httpx.Response(200, json={"dados": payloads[path], "links": []})
        return httpx.Response(404, json={"erro": path})

    return handler


@pytest.fixture
def api_calls() -> list[str]:
    """Lista que acumula os caminhos requisitados à API simulada."""
    return []


@pytest.fixture
def fake_client(tmp_settings: Settings, api_calls: list[str]) -> CamaraClient:
    """Cliente apontado para a API simulada."""
    return CamaraClient(
        tmp_settings.ingestion, transport=httpx.MockTransport(build_api_handler(api_calls))
    )
