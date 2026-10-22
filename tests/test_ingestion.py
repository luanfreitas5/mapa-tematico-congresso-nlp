"""Testes da ingestão e da camada bronze (idempotência, manifesto, cache)."""

import json
import time
from datetime import date

import httpx
import polars as pl
import pytest

from exceptions.data import DataNotFoundError, IngestionError
from ingestion.client import CamaraClient
from ingestion.runner import SOURCE_ORDER, build_labels, run_ingestion
from ingestion.sources import fetch_votes, map_parallel, normalize_record
from storage.bronze import BronzeStore


def test_normalize_record_serializes_nested_values():
    """Valores aninhados viram JSON; escalares permanecem."""
    result = normalize_record({"id": 1, "fase": {"titulo": "x"}, "tags": ["a"]})
    assert result == {"id": 1, "fase": '{"titulo": "x"}', "tags": '["a"]'}


@pytest.mark.integration
def test_run_ingestion_writes_all_sources_and_is_idempotent(tmp_settings, fake_client, api_calls):
    """Todas as fontes vão para a bronze; a segunda execução usa o cache sem chamar a API."""
    first = run_ingestion(tmp_settings, client=fake_client)
    assert set(first) == set(SOURCE_ORDER)
    assert all(path.is_file() for path in first.values())
    calls_after_first = len(api_calls)

    second = run_ingestion(tmp_settings, client=fake_client)
    assert second == first
    assert len(api_calls) == calls_after_first


@pytest.mark.integration
def test_manifest_records_hash_and_rows(tmp_settings, fake_client):
    """O manifesto registra fonte, linhas e SHA-256 de cada snapshot."""
    run_ingestion(tmp_settings, selected=["deputies"], client=fake_client)
    manifest = json.loads((tmp_settings.paths.bronze / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 1
    assert manifest[0]["source"] == "deputies"
    assert manifest[0]["rows"] == 1
    assert len(manifest[0]["sha256"]) == 64
    assert "user_agent" not in manifest[0]["params"]


def test_dependent_source_without_prerequisite_fails(tmp_settings, fake_client):
    """Pedir 'authors' sem 'propositions' ingeridas levanta DataNotFoundError."""
    with pytest.raises(DataNotFoundError):
        run_ingestion(tmp_settings, selected=["authors"], client=fake_client)


def test_unknown_source_is_rejected(tmp_settings, fake_client):
    """Fonte desconhecida é erro de uso."""
    with pytest.raises(ValueError, match="desconhecidas"):
        run_ingestion(tmp_settings, selected=["inexistente"], client=fake_client)


def test_labels_are_stable(tmp_settings):
    """Rótulos de cache derivam só da configuração."""
    labels = build_labels(tmp_settings)
    assert labels["deputies"] == "legislatura-57"
    assert labels["propositions"] == "2023-02-01_2023-02-28_PT"


def test_bronze_snapshot_is_immutable_for_same_day(tmp_path):
    """Gravar duas vezes no mesmo dia mantém o snapshot original."""
    store = BronzeStore(tmp_path)
    day = date(2024, 1, 1)
    first = store.write_snapshot(pl.DataFrame({"a": [1]}), "s", "l", {}, snapshot_date=day)
    second = store.write_snapshot(pl.DataFrame({"a": [2]}), "s", "l", {}, snapshot_date=day)
    assert first == second
    assert pl.read_parquet(first)["a"].to_list() == [1]


def test_bronze_latest_snapshot_picks_newest(tmp_path):
    """O snapshot mais recente (por data no nome) é o lido."""
    store = BronzeStore(tmp_path)
    store.write_snapshot(pl.DataFrame({"a": [1]}), "s", "l", {}, snapshot_date=date(2024, 1, 1))
    store.write_snapshot(pl.DataFrame({"a": [2]}), "s", "l", {}, snapshot_date=date(2024, 2, 1))
    assert store.read_latest("s", "l")["a"].to_list() == [2]


def test_bronze_rejects_empty_frame_and_missing_snapshot(tmp_path):
    """DataFrame sem colunas e leitura sem snapshot geram erros do domínio."""
    store = BronzeStore(tmp_path)
    with pytest.raises(IngestionError):
        store.write_snapshot(pl.DataFrame(), "s", "l", {})
    with pytest.raises(DataNotFoundError):
        store.read_latest("s", "l")


def test_fetch_votes_treats_404_as_no_votes(tmp_settings):
    """Votação com HTTP 404 em /votos rende lista vazia; as demais seguem normalmente."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "/gone/" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(
            200,
            json={
                "dados": [
                    {
                        "tipoVoto": "Sim",
                        "deputado_": {"id": 7, "siglaPartido": "X", "siglaUf": "SP"},
                    }
                ],
                "links": [],
            },
        )

    with CamaraClient(tmp_settings.ingestion, transport=httpx.MockTransport(handler)) as client:
        rows = fetch_votes(client, ["ok", "gone"], max_workers=2)
    assert [r["idVotacao"] for r in rows] == ["ok"]


def test_map_parallel_cancels_pending_on_failure():
    """Ao falhar um item, o erro é propagado sem executar todas as tarefas pendentes."""
    executed: list[int] = []

    def func(item: int) -> list[dict]:
        executed.append(item)
        if item == 0:
            raise IngestionError("falha")
        time.sleep(0.05)
        return []

    with pytest.raises(IngestionError):
        map_parallel(func, range(200), max_workers=2, description="teste")
    assert len(executed) < 200
