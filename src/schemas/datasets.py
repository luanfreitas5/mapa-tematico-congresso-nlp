"""Contratos de dados das camadas silver e gold."""

import pandera.polars as pa
import polars as pl
from pandera.errors import SchemaError, SchemaErrors

from exceptions.data import DataValidationError

DEPUTIES_SCHEMA = pa.DataFrameSchema(
    {
        "deputy_id": pa.Column(pl.Int64, pa.Check.greater_than(0), unique=True),
        "name": pa.Column(pl.String),
        "party": pa.Column(pl.String, nullable=True),
        "state": pa.Column(pl.String, nullable=True),
        "legislature_id": pa.Column(pl.Int64, nullable=True),
    },
    strict=True,
)

PROPOSITIONS_SCHEMA = pa.DataFrameSchema(
    {
        "proposition_id": pa.Column(pl.Int64, pa.Check.greater_than(0), unique=True),
        "type_code": pa.Column(pl.String),
        "number": pa.Column(pl.Int64, nullable=True),
        "year": pa.Column(pl.Int64, pa.Check.in_range(1900, 2100)),
        "text": pa.Column(pl.String),
        "text_clean": pa.Column(pl.String),
        "period": pa.Column(pl.Date),
    },
    strict=True,
)

AUTHORS_SCHEMA = pa.DataFrameSchema(
    {
        "proposition_id": pa.Column(pl.Int64, pa.Check.greater_than(0)),
        "deputy_id": pa.Column(pl.Int64, pa.Check.greater_than(0)),
        "signature_order": pa.Column(pl.Int64, nullable=True),
    },
    strict=True,
)

VOTES_SCHEMA = pa.DataFrameSchema(
    {
        "voting_id": pa.Column(pl.String),
        "deputy_id": pa.Column(pl.Int64, pa.Check.greater_than(0)),
        "party": pa.Column(pl.String, nullable=True),
        "vote": pa.Column(pl.String),
    },
    strict=True,
)

SPEECHES_SCHEMA = pa.DataFrameSchema(
    {
        "speech_id": pa.Column(pl.String, unique=True),
        "deputy_id": pa.Column(pl.Int64, pa.Check.greater_than(0)),
        "text": pa.Column(pl.String),
        "text_clean": pa.Column(pl.String),
        "period": pa.Column(pl.Date),
    },
    strict=True,
)

DOC_TOPICS_SCHEMA = pa.DataFrameSchema(
    {
        "doc_id": pa.Column(pl.String, unique=True),
        "topic": pa.Column(pl.Int64, pa.Check.greater_than_or_equal_to(-1)),
        "period": pa.Column(pl.Date),
        "text": pa.Column(pl.String),
    },
    strict=True,
)


def validate_frame(df: pl.DataFrame, schema: pa.DataFrameSchema, name: str) -> pl.DataFrame:
    """Valida um DataFrame contra um contrato de dados.

    Parameters
    ----------
    df : pl.DataFrame
        Dados a validar.
    schema : pa.DataFrameSchema
        Contrato esperado.
    name : str
        Nome do conjunto, usado na mensagem de erro.

    Returns
    -------
    pl.DataFrame
        O mesmo DataFrame, validado.

    Raises
    ------
    DataValidationError
        Se os dados violarem o contrato.

    Examples
    --------
    >>> validate_frame(deputies, DEPUTIES_SCHEMA, "deputados silver")
    """
    try:
        return schema.validate(df)
    except (SchemaError, SchemaErrors) as exc:
        raise DataValidationError(f"Contrato violado em '{name}': {exc}") from exc
