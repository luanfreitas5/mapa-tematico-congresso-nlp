"""Caminhos fixos do repositório."""

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[2]
CONFIGS_DIR: Path = ROOT / "configs"
