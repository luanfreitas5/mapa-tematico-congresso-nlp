"""Geração de embeddings com sentence-transformers e cache em disco."""

import json
import logging
from pathlib import Path

import numpy as np

from config.settings import EmbeddingsParams
from utils.hashing import hash_texts

logger = logging.getLogger(__name__)


def encode_texts(texts: list[str], params: EmbeddingsParams) -> np.ndarray:
    """Codifica textos em vetores densos com um modelo sentence-transformers.

    Parameters
    ----------
    texts : list[str]
        Textos a codificar.
    params : EmbeddingsParams
        Modelo, tamanho de lote, normalização e dispositivo.

    Returns
    -------
    np.ndarray
        Matriz ``(len(texts), dimensão)`` em ``float32``.

    Raises
    ------
    ImportError
        Se o extra ``nlp`` não estiver instalado.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError("Instale o extra de PLN: uv sync --extra nlp") from exc

    embeddings = SentenceTransformer(params.model_name, device=params.device).encode(
        texts,
        batch_size=params.batch_size,
        show_progress_bar=True,
        normalize_embeddings=params.normalize,
        convert_to_numpy=True,
    )
    return np.asarray(embeddings, dtype=np.float32)


def load_or_encode(texts: list[str], params: EmbeddingsParams, cache_path: Path) -> np.ndarray:
    """Reaproveita embeddings em cache se modelo e textos forem idênticos.

    O cache grava ``<cache_path>`` (``.npy``) e ``<cache_path>.json`` com o hash
    de ``(modelo, normalização, textos)``; qualquer mudança invalida o cache.

    Parameters
    ----------
    texts : list[str]
        Textos a codificar.
    params : EmbeddingsParams
        Parâmetros do encoder.
    cache_path : Path
        Arquivo ``.npy`` de cache.

    Returns
    -------
    np.ndarray
        Embeddings, do cache ou recém-calculados.
    """
    meta_path = cache_path.with_suffix(".json")
    key = hash_texts(f"{params.model_name}|{params.normalize}", texts)
    if cache_path.is_file() and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("key") == key:
            logger.info("Embeddings em cache reutilizados: %s", cache_path)
            return np.load(cache_path)
    embeddings = encode_texts(texts, params)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, embeddings)
    meta_path.write_text(
        json.dumps({"key": key, "model": params.model_name, "rows": len(texts)}), encoding="utf-8"
    )
    return embeddings
