"""Transformações bronze → silver: tipagem, limpeza, deduplicação e validação."""

import polars as pl

from constants.columns import DEPUTIES_RENAME
from preprocessing.text import build_clean_text_expr, count_tokens_expr
from schemas.datasets import (
    AUTHORS_SCHEMA,
    DEPUTIES_SCHEMA,
    PROPOSITIONS_SCHEMA,
    SPEECHES_SCHEMA,
    VOTES_SCHEMA,
    validate_frame,
)


def build_silver_deputies(bronze: pl.DataFrame) -> pl.DataFrame:
    """Constrói a tabela silver de deputados.

    Remove campos pessoais desnecessários à análise (e-mail, foto, URIs).

    Parameters
    ----------
    bronze : pl.DataFrame
        Snapshot bronze de ``/deputados``.

    Returns
    -------
    pl.DataFrame
        Tabela validada por ``DEPUTIES_SCHEMA``.

    Raises
    ------
    DataValidationError
        Se o resultado violar o contrato.
    """
    silver = (
        bronze.select(list(DEPUTIES_RENAME))
        .rename(DEPUTIES_RENAME)
        .with_columns(
            pl.col("deputy_id").cast(pl.Int64),
            pl.col("legislature_id").cast(pl.Int64),
        )
        .unique(subset="deputy_id", keep="last", maintain_order=True)
    )
    return validate_frame(silver, DEPUTIES_SCHEMA, "deputados (silver)")


def build_silver_propositions(bronze: pl.DataFrame, min_tokens: int) -> pl.DataFrame:
    """Constrói a tabela silver de proposições a partir das ementas.

    Parameters
    ----------
    bronze : pl.DataFrame
        Snapshot bronze de ``/proposicoes`` (com ``window_start``).
    min_tokens : int
        Ementas limpas com menos tokens são descartadas.

    Returns
    -------
    pl.DataFrame
        Tabela validada por ``PROPOSITIONS_SCHEMA``.

    Raises
    ------
    DataValidationError
        Se o resultado violar o contrato.
    """
    silver = (
        bronze.select(
            pl.col("id").cast(pl.Int64).alias("proposition_id"),
            pl.col("siglaTipo").cast(pl.String).alias("type_code"),
            pl.col("numero").cast(pl.Int64, strict=False).alias("number"),
            pl.col("ano").cast(pl.Int64).alias("year"),
            pl.col("ementa").cast(pl.String).fill_null("").str.strip_chars().alias("text"),
            pl.col("window_start").str.to_date("%Y-%m-%d").alias("period"),
        )
        .with_columns(build_clean_text_expr("text").alias("text_clean"))
        .filter(count_tokens_expr("text_clean") >= min_tokens)
        .unique(subset="proposition_id", keep="first", maintain_order=True)
        .select(list(PROPOSITIONS_SCHEMA.columns))
    )
    return validate_frame(silver, PROPOSITIONS_SCHEMA, "proposições (silver)")


def build_silver_authors(bronze: pl.DataFrame) -> pl.DataFrame:
    """Constrói a tabela silver de autoria, mantendo apenas autores que são deputados.

    O identificador do deputado é extraído da URI do autor
    (``.../deputados/<id>``); autores institucionais (órgãos, Executivo) são descartados.

    Parameters
    ----------
    bronze : pl.DataFrame
        Snapshot bronze de ``/proposicoes/{id}/autores``.

    Returns
    -------
    pl.DataFrame
        Tabela validada por ``AUTHORS_SCHEMA``.

    Raises
    ------
    DataValidationError
        Se o resultado violar o contrato.
    """
    silver = (
        bronze.select(
            pl.col("idProposicao").cast(pl.Int64).alias("proposition_id"),
            pl.col("uri").str.extract(r"/deputados/(\d+)$", 1).cast(pl.Int64).alias("deputy_id"),
            pl.col("ordemAssinatura").cast(pl.Int64, strict=False).alias("signature_order"),
        )
        .drop_nulls(["proposition_id", "deputy_id"])
        .unique(subset=["proposition_id", "deputy_id"], keep="first", maintain_order=True)
    )
    return validate_frame(silver, AUTHORS_SCHEMA, "autores (silver)")


def build_silver_votes(bronze: pl.DataFrame) -> pl.DataFrame:
    """Constrói a tabela silver de votos nominais.

    Parameters
    ----------
    bronze : pl.DataFrame
        Snapshot bronze de ``/votacoes/{id}/votos`` (já achatado na ingestão).

    Returns
    -------
    pl.DataFrame
        Tabela validada por ``VOTES_SCHEMA``.

    Raises
    ------
    DataValidationError
        Se o resultado violar o contrato.
    """
    silver = (
        bronze.select(
            pl.col("idVotacao").cast(pl.String).alias("voting_id"),
            pl.col("idDeputado").cast(pl.Int64, strict=False).alias("deputy_id"),
            pl.col("siglaPartido").cast(pl.String).alias("party"),
            pl.col("tipoVoto").cast(pl.String).alias("vote"),
        )
        .drop_nulls(["voting_id", "deputy_id", "vote"])
        .unique(subset=["voting_id", "deputy_id"], keep="first", maintain_order=True)
    )
    return validate_frame(silver, VOTES_SCHEMA, "votos (silver)")


def build_silver_speeches(bronze: pl.DataFrame, min_tokens: int, max_chars: int) -> pl.DataFrame:
    """Constrói a tabela silver de discursos.

    Usa a transcrição; se ausente, o sumário. Textos são truncados em ``max_chars``.

    Parameters
    ----------
    bronze : pl.DataFrame
        Snapshot bronze de ``/deputados/{id}/discursos``.
    min_tokens : int
        Discursos limpos com menos tokens são descartados.
    max_chars : int
        Tamanho máximo do texto mantido.

    Returns
    -------
    pl.DataFrame
        Tabela validada por ``SPEECHES_SCHEMA``.

    Raises
    ------
    DataValidationError
        Se o resultado violar o contrato.
    """
    started = pl.col("dataHoraInicio").cast(pl.String)
    transcript = pl.col("transcricao").cast(pl.String)
    raw_text = pl.coalesce(
        pl.when(transcript.str.len_chars() > 0).then(transcript),
        pl.col("sumario").cast(pl.String),
    ).fill_null("")
    silver = (
        bronze.select(
            pl.concat_str([pl.col("idDeputado").cast(pl.String), started], separator="|").alias(
                "speech_id"
            ),
            pl.col("idDeputado").cast(pl.Int64).alias("deputy_id"),
            raw_text.str.strip_chars().str.slice(0, max_chars).alias("text"),
            started.str.slice(0, 10)
            .str.to_date("%Y-%m-%d", strict=False)
            .dt.truncate("1mo")
            .alias("period"),
        )
        .drop_nulls(["period"])
        .with_columns(build_clean_text_expr("text").alias("text_clean"))
        .filter(count_tokens_expr("text_clean") >= min_tokens)
        .unique(subset="speech_id", keep="first", maintain_order=True)
        .select(list(SPEECHES_SCHEMA.columns))
    )
    return validate_frame(silver, SPEECHES_SCHEMA, "discursos (silver)")
