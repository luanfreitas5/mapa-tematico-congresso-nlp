"""Testes de utilitários: datas, hashes e estatística."""

import itertools
from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from utils.dates import generate_month_windows
from utils.hashing import hash_file, hash_texts
from utils.statistics import bootstrap_mean_interval, wilson_interval


def test_month_windows_split_at_month_boundaries():
    """Cada janela termina no fim do mês ou do período."""
    windows = generate_month_windows(date(2023, 1, 15), date(2023, 3, 10))
    assert windows == [
        (date(2023, 1, 15), date(2023, 1, 31)),
        (date(2023, 2, 1), date(2023, 2, 28)),
        (date(2023, 3, 1), date(2023, 3, 10)),
    ]


def test_month_windows_rejects_inverted_period():
    """Período invertido é erro."""
    with pytest.raises(ValueError):
        generate_month_windows(date(2023, 2, 1), date(2023, 1, 1))


@given(
    start=st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31)),
    days=st.integers(min_value=0, max_value=800),
)
def test_month_windows_are_contiguous_and_cover_period(start, days):
    """Invariante: janelas contíguas, sem lacunas, cobrindo exatamente [start, end]."""
    end = start + timedelta(days=days)
    windows = generate_month_windows(start, end)
    assert windows[0][0] == start
    assert windows[-1][1] == end
    for (_, previous_end), (next_start, _) in itertools.pairwise(windows):
        assert next_start == previous_end + timedelta(days=1)


def test_hash_texts_is_order_sensitive_and_deterministic():
    """O hash depende da ordem e do prefixo, e é estável."""
    assert hash_texts("m", ["a", "b"]) == hash_texts("m", ["a", "b"])
    assert hash_texts("m", ["a", "b"]) != hash_texts("m", ["b", "a"])
    assert hash_texts("m", ["a"]) != hash_texts("n", ["a"])


def test_hash_file_changes_with_content(tmp_path):
    """O hash do arquivo muda quando o conteúdo muda."""
    path = tmp_path / "f.txt"
    path.write_text("a", encoding="utf-8")
    first = hash_file(path)
    path.write_text("b", encoding="utf-8")
    assert hash_file(path) != first


def test_bootstrap_interval_brackets_mean_for_spread_data():
    """Para dados dispersos, o IC contém a média e é reprodutível."""
    values = [0.2, 0.4, 0.5, 0.6, 0.9]
    mean, low, high = bootstrap_mean_interval(values, n_resamples=500, seed=1)
    assert low <= mean <= high
    assert bootstrap_mean_interval(values, n_resamples=500, seed=1) == (mean, low, high)


def test_bootstrap_rejects_bad_inputs():
    """Entrada vazia ou nível de confiança inválido são erros."""
    with pytest.raises(ValueError):
        bootstrap_mean_interval([])
    with pytest.raises(ValueError):
        bootstrap_mean_interval([1.0], confidence=1.5)


@given(total=st.integers(min_value=1, max_value=500), data=st.data())
def test_wilson_interval_is_ordered_and_bounded(total, data):
    """Invariante: 0 <= inferior <= proporção <= superior <= 1 (com tolerância numérica)."""
    successes = data.draw(st.integers(min_value=0, max_value=total))
    p, low, high = wilson_interval(successes, total)
    eps = 1e-9
    assert -eps <= low <= p + eps
    assert p - eps <= high <= 1 + eps


def test_wilson_rejects_bad_inputs():
    """Total não positivo, sucessos fora da faixa e confiança não suportada falham."""
    with pytest.raises(ValueError):
        wilson_interval(1, 0)
    with pytest.raises(ValueError):
        wilson_interval(5, 3)
    with pytest.raises(ValueError):
        wilson_interval(1, 3, confidence=0.5)
