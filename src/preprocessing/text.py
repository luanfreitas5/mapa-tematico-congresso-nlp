"""Limpeza leve de textos em português (ementas e discursos).

A limpeza preserva a sintaxe (sem remoção de stopwords nem stemming), pois o
encoder de sentenças se beneficia de frases completas; stopwords são tratadas
apenas na vetorização c-TF-IDF.
"""

import re
import unicodedata

import polars as pl

from constants.regex import (
    DIGITS_PATTERN,
    LEGAL_NUMBER_PATTERN,
    NON_WORD_PATTERN,
    URL_PATTERN,
    WHITESPACE_PATTERN,
)

_STEPS: tuple[str, ...] = (
    URL_PATTERN,
    LEGAL_NUMBER_PATTERN,
    DIGITS_PATTERN,
    NON_WORD_PATTERN,
)
_COMPILED_STEPS = tuple(re.compile(pattern) for pattern in _STEPS)
_WHITESPACE = re.compile(WHITESPACE_PATTERN)


def clean_text(text: str | None) -> str:
    """Normaliza um texto: minúsculas, sem URLs, números legais, dígitos e pontuação.

    Parameters
    ----------
    text : str | None
        Texto bruto; ``None`` é tratado como vazio.

    Returns
    -------
    str
        Texto limpo, com espaços normalizados.

    Examples
    --------
    >>> clean_text("Altera a Lei nº 8.666, de 21 de junho de 1993, sobre licitações!")
    'altera a lei sobre licitações'
    """
    if not text:
        return ""
    value = unicodedata.normalize("NFC", text).lower()
    for pattern in _COMPILED_STEPS:
        value = pattern.sub(" ", value)
    return _WHITESPACE.sub(" ", value).strip()


def build_clean_text_expr(column: str) -> pl.Expr:
    """Equivalente vetorizado de :func:`clean_text` para uso em ``with_columns``.

    Parameters
    ----------
    column : str
        Coluna de texto bruto.

    Returns
    -------
    pl.Expr
        Expressão que produz o texto limpo.

    Examples
    --------
    >>> df.with_columns(build_clean_text_expr("text").alias("text_clean"))
    """
    expr = pl.col(column).cast(pl.String).fill_null("").str.to_lowercase()
    for pattern in _STEPS:
        expr = expr.str.replace_all(pattern, " ")
    return expr.str.replace_all(WHITESPACE_PATTERN, " ").str.strip_chars()


def count_tokens_expr(column: str) -> pl.Expr:
    """Conta tokens (separados por espaço) de uma coluna já limpa.

    Parameters
    ----------
    column : str
        Coluna de texto limpo.

    Returns
    -------
    pl.Expr
        Expressão com o número de tokens (0 para texto vazio).
    """
    return (
        pl.when(pl.col(column).str.len_chars() > 0)
        .then(pl.col(column).str.split(" ").list.len().cast(pl.Int64))
        .otherwise(pl.lit(0, dtype=pl.Int64))
    )
