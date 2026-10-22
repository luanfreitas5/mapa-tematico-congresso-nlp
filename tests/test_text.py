"""Testes da limpeza de textos (exemplos e propriedades)."""

import re

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from preprocessing.text import build_clean_text_expr, clean_text, count_tokens_expr


@pytest.mark.smoke
def test_clean_text_removes_legal_numbers_and_punctuation():
    """Números legais, datas por extenso e pontuação são removidos."""
    text = "Altera a Lei nº 8.666, de 21 de junho de 1993, sobre licitações!"
    assert clean_text(text) == "altera a lei sobre licitações"


def test_clean_text_handles_none_and_empty():
    """None e vazio resultam em string vazia."""
    assert clean_text(None) == ""
    assert clean_text("") == ""


def test_clean_text_removes_urls_and_digits():
    """URLs e dígitos soltos não sobrevivem."""
    assert clean_text("Veja https://x.com/a ok 123") == "veja ok"


def test_expression_matches_python_function():
    """A versão vetorizada produz o mesmo resultado que a função Python."""
    values = ["Altera a Lei nº 8.666, de 21 de junho de 1993!", None, "Veja https://x.com/a ok 123"]
    result = pl.DataFrame({"text": values}).select(build_clean_text_expr("text"))["text"].to_list()
    assert result == [clean_text(value) for value in values]


def test_count_tokens_expr():
    """Texto vazio tem 0 tokens; caso contrário, conta palavras."""
    df = pl.DataFrame({"t": ["", "a b c"]})
    assert df.select(count_tokens_expr("t"))["t"].to_list() == [0, 3]


@given(st.text())
def test_clean_text_is_whitespace_normalized_and_digit_free(text):
    """Invariantes: sem espaços redundantes e sem dígitos, para qualquer entrada."""
    cleaned = clean_text(text)
    assert cleaned == " ".join(cleaned.split())
    assert not re.search(r"\d", cleaned)
