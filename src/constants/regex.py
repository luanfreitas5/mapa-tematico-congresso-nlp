"""Padrões regex da limpeza de textos (compatíveis com ``re`` e com o Polars/Rust)."""

URL_PATTERN = r"https?://\S+|www\.\S+"

# "nº 8.666, de 21 de junho de 1993", "n° 14/2020", "no 123, de 2019"
LEGAL_NUMBER_PATTERN = (
    r"\bn[º°o]\.?\s*[\d.]+(?:/\d+)?"
    r"(?:,?\s+de\s+(?:\d{1,2}\s+de\s+[a-zç]+\s+de\s+)?\d{4})?"
)

DIGITS_PATTERN = r"\d+"
NON_WORD_PATTERN = r"[^\w\s]|_"
WHITESPACE_PATTERN = r"\s+"
