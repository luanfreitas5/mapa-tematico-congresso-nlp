"""Leitura e escrita de arquivos Parquet."""

import logging
from pathlib import Path

import polars as pl

from exceptions.data import DataNotFoundError

logger = logging.getLogger(__name__)


def write_parquet(df: pl.DataFrame, path: Path) -> Path:
    """Grava um DataFrame em Parquet (zstd), criando os diretórios necessários.

    Parameters
    ----------
    df : pl.DataFrame
        Dados a gravar.
    path : Path
        Arquivo de destino.

    Returns
    -------
    Path
        O próprio ``path``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path, compression="zstd")
    logger.info("Gravado %s (%d linhas)", path, df.height)
    return path


def read_parquet(path: Path) -> pl.DataFrame:
    """Lê um arquivo Parquet.

    Parameters
    ----------
    path : Path
        Arquivo de origem.

    Returns
    -------
    pl.DataFrame
        Dados lidos.

    Raises
    ------
    DataNotFoundError
        Se o arquivo não existir (etapa anterior ainda não executada).
    """
    if not path.is_file():
        raise DataNotFoundError(f"Arquivo não encontrado: {path}. Execute a etapa anterior.")
    return pl.read_parquet(path)
