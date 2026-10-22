"""Reprodutibilidade: sementes e variáveis de ambiente."""

import os
import random
from contextlib import suppress

import numpy as np


def seed_everything(seed: int = 42) -> None:
    """Fixa as fontes de aleatoriedade do processo.

    ``PYTHONHASHSEED`` só tem efeito pleno se exportado antes do interpretador
    iniciar (o Makefile faz isso); aqui ele é definido para subprocessos.

    Parameters
    ----------
    seed : int, optional
        Semente global, by default 42.

    Examples
    --------
    >>> seed_everything(42)
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)  # noqa: NPY002 - semente global para bibliotecas legadas
    with suppress(ImportError):
        import torch

        torch.manual_seed(seed)
