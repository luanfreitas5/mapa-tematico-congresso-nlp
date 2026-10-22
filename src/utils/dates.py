"""Utilitários de datas."""

from datetime import date, timedelta


def generate_month_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Divide um período em janelas mensais contíguas, limitadas por ``start`` e ``end``.

    Parameters
    ----------
    start : date
        Primeiro dia do período (inclusivo).
    end : date
        Último dia do período (inclusivo).

    Returns
    -------
    list[tuple[date, date]]
        Pares ``(início, fim)`` inclusivos, um por mês civil tocado pelo período.

    Raises
    ------
    ValueError
        Se ``start`` for posterior a ``end``.

    Examples
    --------
    >>> windows = generate_month_windows(date(2023, 1, 15), date(2023, 2, 10))
    >>> windows[0][1], windows[1][0]
    (datetime.date(2023, 1, 31), datetime.date(2023, 2, 1))
    """
    if start > end:
        raise ValueError("start deve ser anterior ou igual a end")
    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        next_month = (cursor.replace(day=1) + timedelta(days=32)).replace(day=1)
        windows.append((cursor, min(next_month - timedelta(days=1), end)))
        cursor = next_month
    return windows
