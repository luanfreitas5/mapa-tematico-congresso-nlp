"""Exceções relacionadas a dados e ingestão."""

from exceptions.base import ProjectError


class IngestionError(ProjectError):
    """Falha ao consultar a API ou ao persistir dados brutos."""


class ResourceNotFoundError(IngestionError):
    """A API respondeu HTTP 404: o recurso consultado não existe (mais)."""


class DataNotFoundError(ProjectError):
    """Camada de dados esperada ainda não foi produzida."""


class DataValidationError(ProjectError):
    """Dados violam o contrato (schema) da camada."""
