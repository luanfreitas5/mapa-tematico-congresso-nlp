"""Configuração de logging com ``rich`` e rotação diária de arquivos."""

import logging
from datetime import date
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

from config.settings import LoggingConfig


def configure_logging(config: LoggingConfig, log_dir: Path) -> None:
    """Configura os handlers de console (rich) e de arquivo com rotação diária.

    Parameters
    ----------
    config : LoggingConfig
        Nível, retenção e formato do arquivo de log.
    log_dir : Path
        Diretório onde ``log_YYYY-MM-DD.log`` será gravado.

    Examples
    --------
    >>> configure_logging(settings.logging, settings.paths.logs)
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        log_dir / f"log_{date.today():%Y-%m-%d}.log",
        when="midnight",
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(config.file_format))
    logging.basicConfig(
        level=config.level,
        format="%(name)s - %(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False), file_handler],
        force=True,
    )
