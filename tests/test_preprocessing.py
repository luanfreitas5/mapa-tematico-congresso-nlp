"""Testes das transformações bronze → silver e dos contratos de dados."""

import polars as pl
import pytest

from exceptions.data import DataValidationError
from preprocessing import pipeline
from schemas.datasets import DEPUTIES_SCHEMA, validate_frame


def test_silver_deputies_drops_pii_columns_and_deduplicates():
    """E-mail e foto não chegam à silver; ids duplicados são colapsados."""
    bronze = pl.DataFrame(
        {
            "id": [1, 1, 2],
            "nome": ["Ana", "Ana", "Bia"],
            "siglaPartido": ["AAA", "AAA", "BBB"],
            "siglaUf": ["SP", "SP", "RJ"],
            "idLegislatura": [57, 57, 57],
            "email": ["a@x.org", "a@x.org", "b@x.org"],
            "urlFoto": ["u1", "u1", "u2"],
        }
    )
    silver = pipeline.build_silver_deputies(bronze)
    assert silver.columns == ["deputy_id", "name", "party", "state", "legislature_id"]
    assert silver["deputy_id"].to_list() == [1, 2]


def test_silver_propositions_filters_short_and_duplicate_summaries():
    """Ementas curtas e ids repetidos são removidos; o texto limpo é gerado."""
    bronze = pl.DataFrame(
        {
            "id": [1, 2, 2],
            "siglaTipo": ["PL", "PL", "PL"],
            "numero": [1, 2, 2],
            "ano": [2023, 2023, 2023],
            "ementa": [
                "Altera a Lei nº 8.666, de 1993, para dispor sobre licitações públicas.",
                "Curta.",
                "Curta.",
            ],
            "window_start": ["2023-02-01"] * 3,
        }
    )
    silver = pipeline.build_silver_propositions(bronze, min_tokens=5)
    assert silver["proposition_id"].to_list() == [1]
    assert silver["text_clean"][0] == "altera a lei para dispor sobre licitações públicas"


def test_silver_authors_keeps_only_deputies():
    """Autores institucionais (URI sem /deputados/) são descartados."""
    bronze = pl.DataFrame(
        {
            "idProposicao": [10, 10, 11],
            "uri": [
                "https://dadosabertos.camara.leg.br/api/v2/deputados/1",
                "https://dadosabertos.camara.leg.br/api/v2/orgaos/5",
                "https://dadosabertos.camara.leg.br/api/v2/deputados/2",
            ],
            "ordemAssinatura": [1, 2, 1],
        }
    )
    silver = pipeline.build_silver_authors(bronze)
    assert silver.select("proposition_id", "deputy_id").rows() == [(10, 1), (11, 2)]


def test_silver_votes_drops_null_ids_and_duplicates():
    """Votos sem deputado ou repetidos por votação são removidos."""
    bronze = pl.DataFrame(
        {
            "idVotacao": ["V1", "V1", "V1"],
            "idDeputado": [1, 1, None],
            "siglaPartido": ["AAA", "AAA", "BBB"],
            "tipoVoto": ["Sim", "Sim", "Não"],
        }
    )
    silver = pipeline.build_silver_votes(bronze)
    assert silver.height == 1


def test_silver_speeches_prefers_transcript_and_truncates():
    """Usa a transcrição quando existe; senão o sumário; trunca e filtra por tamanho."""
    long_text = " ".join(["economia"] * 50)
    bronze = pl.DataFrame(
        {
            "idDeputado": [1, 1, 2],
            "dataHoraInicio": ["2023-03-15T10:00", "2023-03-16T10:00", "2023-03-17T10:00"],
            "transcricao": [long_text, None, "curto"],
            "sumario": ["resumo", long_text, "resumo"],
        }
    )
    silver = pipeline.build_silver_speeches(bronze, min_tokens=30, max_chars=400)
    assert silver.height == 2
    assert all(len(text) <= 400 for text in silver["text"])
    assert silver["period"].dt.day().unique().to_list() == [1]


def test_validate_frame_raises_domain_error_on_violation():
    """Violações de contrato viram DataValidationError."""
    invalid = pl.DataFrame(
        {
            "deputy_id": [-1],
            "name": ["x"],
            "party": ["A"],
            "state": ["SP"],
            "legislature_id": [57],
        }
    )
    with pytest.raises(DataValidationError):
        validate_frame(invalid, DEPUTIES_SCHEMA, "teste")
