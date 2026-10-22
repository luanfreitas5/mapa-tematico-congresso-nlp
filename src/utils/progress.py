"""Barras de progresso padronizadas (rich)."""

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


def create_progress() -> Progress:
    """Cria a barra de progresso padrão do projeto.

    Returns
    -------
    Progress
        Instância pronta para uso como gerenciador de contexto.

    Examples
    --------
    >>> with create_progress() as progress:
    ...     task = progress.add_task("Processando", total=10)
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )
