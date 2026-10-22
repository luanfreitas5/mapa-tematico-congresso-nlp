"""Testes da validação de configuração."""

import shutil
from pathlib import Path

import pytest

from config.paths import CONFIGS_DIR
from config.settings import load_settings
from exceptions.configuration import ConfigurationError


@pytest.mark.smoke
def test_load_settings_defaults(base_settings):
    """Os YAML versionados formam uma configuração válida e com caminhos absolutos."""
    assert base_settings.random_seed == 42
    assert base_settings.paths.bronze.is_absolute()
    assert base_settings.model.umap.n_components > 0


def _copy_configs(tmp_path: Path) -> Path:
    """Copia ``configs/`` para um diretório temporário editável."""
    target = tmp_path / "configs"
    shutil.copytree(CONFIGS_DIR, target)
    return target


def test_invalid_period_raises(tmp_path):
    """Período com início posterior ao fim falha na carga, não no meio da execução."""
    directory = _copy_configs(tmp_path)
    config = directory / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "start_date: 2023-02-01", "start_date: 2030-01-01"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        load_settings(directory)


def test_unknown_key_is_rejected(tmp_path):
    """Chaves desconhecidas são proibidas (extra='forbid')."""
    directory = _copy_configs(tmp_path)
    config = directory / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8") + "\nchave_inesperada: 1\n", encoding="utf-8"
    )
    with pytest.raises(ConfigurationError):
        load_settings(directory)


def test_missing_file_raises(tmp_path):
    """Arquivo ausente gera erro de configuração com mensagem clara."""
    with pytest.raises(ConfigurationError, match="não encontrado"):
        load_settings(tmp_path)


def test_invalid_yaml_raises(tmp_path):
    """YAML malformado é convertido em ConfigurationError."""
    directory = _copy_configs(tmp_path)
    (directory / "paths.yaml").write_text("bronze: [", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="YAML inválido"):
        load_settings(directory)
