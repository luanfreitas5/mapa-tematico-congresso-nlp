"""Funções de hash para rastrear versões de dados e chaves de cache."""

import hashlib
from collections.abc import Iterable
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def hash_file(path: Path) -> str:
    """Calcula o SHA-256 de um arquivo, lendo-o em blocos.

    Parameters
    ----------
    path : Path
        Caminho do arquivo.

    Returns
    -------
    str
        Digest hexadecimal.

    Raises
    ------
    FileNotFoundError
        Se o arquivo não existir.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def hash_texts(prefix: str, texts: Iterable[str]) -> str:
    """Calcula o SHA-256 de uma sequência de textos, sensível à ordem.

    Parameters
    ----------
    prefix : str
        Contexto que também define a chave (ex.: nome do modelo de embeddings).
    texts : Iterable[str]
        Textos a incluir no hash.

    Returns
    -------
    str
        Digest hexadecimal.

    Examples
    --------
    >>> hash_texts("modelo", ["a", "b"]) == hash_texts("modelo", ["a", "b"])
    True
    """
    digest = hashlib.sha256(prefix.encode("utf-8"))
    for text in texts:
        digest.update(b"\x00")
        digest.update(text.encode("utf-8"))
    return digest.hexdigest()
