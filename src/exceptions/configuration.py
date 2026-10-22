"""Exceções de configuração."""

from exceptions.base import ProjectError


class ConfigurationError(ProjectError):
    """Configuração ausente, malformada ou que viola o esquema."""
