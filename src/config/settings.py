"""Carregamento e validação das configurações YAML com Pydantic."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.paths import CONFIGS_DIR, ROOT
from exceptions.configuration import ConfigurationError


class _StrictModel(BaseModel):
    """Base com campos desconhecidos proibidos e instâncias imutáveis."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class IngestionConfig(_StrictModel):
    """Parâmetros da ingestão pela API da Câmara."""

    base_url: str
    legislature_id: int = Field(gt=0)
    start_date: date
    end_date: date
    proposition_types: list[str] = Field(min_length=1)
    page_size: int = Field(gt=0, le=100)
    timeout_seconds: float = Field(gt=0)
    max_retries: int = Field(ge=1)
    backoff_seconds: float = Field(ge=0)
    max_workers: int = Field(ge=1, le=32)
    user_agent: str

    @model_validator(mode="after")
    def _validate_period(self) -> IngestionConfig:
        """Garante que o período de ingestão é cronologicamente válido."""
        if self.start_date > self.end_date:
            raise ValueError("start_date deve ser anterior ou igual a end_date")
        return self


class PreprocessingConfig(_StrictModel):
    """Parâmetros do pré-processamento de textos."""

    min_tokens_summary: int = Field(ge=1)
    min_tokens_speech: int = Field(ge=1)
    max_speech_chars: int = Field(gt=0)


class NetworksConfig(_StrictModel):
    """Parâmetros da construção das redes."""

    max_authors_per_proposition: int = Field(ge=2)
    min_party_members_per_vote: int = Field(ge=1)
    min_common_votings: int = Field(ge=1)
    min_edge_weight: float = Field(ge=0, le=1)


class PathsConfig(_StrictModel):
    """Diretórios do projeto, resolvidos a partir da raiz do repositório."""

    bronze: Path
    silver: Path
    gold: Path
    reports: Path
    figures: Path
    review: Path
    logs: Path

    @field_validator("*", mode="after")
    @classmethod
    def _resolve_against_root(cls, value: Path) -> Path:
        """Converte caminhos relativos em absolutos a partir da raiz."""
        return value if value.is_absolute() else ROOT / value


class LoggingConfig(_StrictModel):
    """Parâmetros de logging."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    backup_count: int = Field(ge=1)
    file_format: str


class EmbeddingsParams(_StrictModel):
    """Parâmetros do encoder de sentenças."""

    model_name: str
    batch_size: int = Field(gt=0)
    normalize: bool
    device: str | None = None


class UmapParams(_StrictModel):
    """Hiperparâmetros do UMAP."""

    n_neighbors: int = Field(gt=1)
    n_components: int = Field(gt=0)
    min_dist: float = Field(ge=0)
    metric: str


class HdbscanParams(_StrictModel):
    """Hiperparâmetros do HDBSCAN."""

    min_cluster_size: int = Field(gt=1)
    min_samples: int = Field(gt=0)
    metric: str
    cluster_selection_method: Literal["eom", "leaf"]


class VectorizerParams(_StrictModel):
    """Parâmetros do CountVectorizer usado no c-TF-IDF."""

    ngram_range: tuple[int, int]
    min_df: int = Field(ge=1)


class BertopicParams(_StrictModel):
    """Parâmetros do BERTopic."""

    top_n_words: int = Field(gt=0)
    nr_topics: int | None = Field(default=None, gt=1)
    reduce_outliers: bool = False


class TopicsOverTimeParams(_StrictModel):
    """Parâmetros da análise temporal de tópicos."""

    nr_bins: int = Field(gt=1)


class EvaluationParams(_StrictModel):
    """Parâmetros de avaliação dos tópicos."""

    coherence_metrics: list[Literal["c_v", "c_npmi", "u_mass", "c_uci"]]
    top_n_words: int = Field(gt=1)
    bootstrap_resamples: int = Field(ge=100)
    review_sample_per_topic: int = Field(ge=1)
    review_max_topics: int = Field(ge=1)


class ModelParams(_StrictModel):
    """Hiperparâmetros agregados de modelagem."""

    embeddings: EmbeddingsParams
    umap: UmapParams
    hdbscan: HdbscanParams
    vectorizer: VectorizerParams
    bertopic: BertopicParams
    topics_over_time: TopicsOverTimeParams
    evaluation: EvaluationParams


class Settings(_StrictModel):
    """Configuração global validada do projeto."""

    version: str
    project_name: str
    random_seed: int
    ingestion: IngestionConfig
    preprocessing: PreprocessingConfig
    networks: NetworksConfig
    paths: PathsConfig
    logging: LoggingConfig
    model: ModelParams


class Secrets(BaseSettings):
    """Segredos opcionais lidos do ambiente / ``.env`` (nunca commitados)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    hf_token: str | None = None


def _read_yaml(path: Path) -> dict[str, Any]:
    """Lê um arquivo YAML e devolve seu conteúdo como dicionário.

    Parameters
    ----------
    path : Path
        Caminho do arquivo YAML.

    Returns
    -------
    dict[str, Any]
        Conteúdo do arquivo.

    Raises
    ------
    ConfigurationError
        Se o arquivo não existir, for inválido ou não for um mapeamento.
    """
    if not path.is_file():
        raise ConfigurationError(f"Arquivo de configuração não encontrado: {path}")
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"YAML inválido em {path}: {exc}") from exc
    if not isinstance(content, dict):
        raise ConfigurationError(f"O arquivo {path} deve conter um mapeamento no topo")
    return content


def load_settings(config_dir: Path | None = None) -> Settings:
    """Carrega os YAML de ``configs/`` e valida a configuração completa.

    Parameters
    ----------
    config_dir : Path, optional
        Diretório com ``config.yaml``, ``paths.yaml``, ``logging.yaml`` e
        ``model_params.yaml``; por padrão, ``configs/`` na raiz do repositório.

    Returns
    -------
    Settings
        Configuração validada e imutável.

    Raises
    ------
    ConfigurationError
        Se algum arquivo estiver ausente ou violar o esquema.

    Examples
    --------
    >>> settings = load_settings()
    >>> settings.random_seed
    42
    """
    directory = config_dir or CONFIGS_DIR
    raw = _read_yaml(directory / "config.yaml")
    raw["paths"] = _read_yaml(directory / "paths.yaml")
    raw["logging"] = _read_yaml(directory / "logging.yaml")
    raw["model"] = _read_yaml(directory / "model_params.yaml")
    try:
        return Settings(**raw)
    except ValidationError as exc:
        raise ConfigurationError(f"Configuração inválida:\n{exc}") from exc
