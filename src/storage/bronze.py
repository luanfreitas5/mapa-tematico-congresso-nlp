"""Camada bronze: snapshots imutáveis, datados e com manifesto de integridade."""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from exceptions.data import DataNotFoundError, IngestionError
from storage.parquet import read_parquet, write_parquet
from utils.hashing import hash_file

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"


class BronzeStore:
    """Gerencia os snapshots da camada bronze.

    Cada snapshot é gravado em ``<root>/<fonte>/<rótulo>__<AAAA-MM-DD>.parquet`` e
    nunca é modificado. O cache é por ``(fonte, rótulo)``: se já existe um
    snapshot, a ingestão é pulada, o que torna a execução idempotente.

    Parameters
    ----------
    root : Path
        Diretório da camada bronze.

    Examples
    --------
    >>> store = BronzeStore(Path("data/bronze"))
    >>> store.latest_snapshot("deputados", "legislatura-57") is None
    True
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def latest_snapshot(self, source: str, label: str) -> Path | None:
        """Retorna o snapshot mais recente de ``(source, label)``, se houver.

        Parameters
        ----------
        source : str
            Nome da fonte (ex.: ``deputados``).
        label : str
            Rótulo dos parâmetros da consulta (ex.: ``2023-02-01_2025-12-31``).

        Returns
        -------
        Path | None
            Caminho do snapshot ou ``None``.
        """
        directory = self.root / source
        if not directory.is_dir():
            return None
        candidates = sorted(directory.glob(f"{label}__*.parquet"))
        return candidates[-1] if candidates else None

    def write_snapshot(
        self,
        df: pl.DataFrame,
        source: str,
        label: str,
        params: dict[str, Any],
        snapshot_date: date | None = None,
    ) -> Path:
        """Grava um novo snapshot e registra-o no manifesto.

        Parameters
        ----------
        df : pl.DataFrame
            Dados exatamente como recebidos da API.
        source : str
            Nome da fonte.
        label : str
            Rótulo dos parâmetros da consulta.
        params : dict[str, Any]
            Parâmetros usados na consulta (rastreabilidade).
        snapshot_date : date, optional
            Data do snapshot; por padrão, hoje.

        Returns
        -------
        Path
            Caminho do snapshot (o existente, se já houver um da mesma data).

        Raises
        ------
        IngestionError
            Se ``df`` não tiver colunas (nenhum registro retornado).
        """
        if df.width == 0:
            raise IngestionError(f"Nenhum registro retornado para {source}/{label}")
        stamp = snapshot_date or date.today()
        path = self.root / source / f"{label}__{stamp.isoformat()}.parquet"
        if path.exists():
            logger.info("Snapshot já existe, mantido: %s", path)
            return path
        write_parquet(df, path)
        self._append_manifest(
            {
                "source": source,
                "label": label,
                "file": path.relative_to(self.root).as_posix(),
                "snapshot_date": stamp.isoformat(),
                "rows": df.height,
                "sha256": hash_file(path),
                "params": params,
            }
        )
        return path

    def read_latest(self, source: str, label: str) -> pl.DataFrame:
        """Lê o snapshot mais recente de ``(source, label)``.

        Parameters
        ----------
        source : str
            Nome da fonte.
        label : str
            Rótulo dos parâmetros da consulta.

        Returns
        -------
        pl.DataFrame
            Dados brutos.

        Raises
        ------
        DataNotFoundError
            Se não houver snapshot.
        """
        path = self.latest_snapshot(source, label)
        if path is None:
            raise DataNotFoundError(
                f"Sem snapshot bronze para {source}/{label}. Execute a etapa de ingestão."
            )
        return read_parquet(path)

    def _append_manifest(self, entry: dict[str, Any]) -> None:
        """Acrescenta uma entrada ao manifesto JSON da camada."""
        manifest_path = self.root / MANIFEST_NAME
        entries: list[dict[str, Any]] = []
        if manifest_path.is_file():
            entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries.append(entry)
        manifest_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
