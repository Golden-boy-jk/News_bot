# app/filters.py
from typing import Iterable, List


def filter_link_by_substring(links: Iterable[str], substring: str) -> List[str]:
    """
    Возвращает только те ссылки, в которых содержится заданная подстрока.
    Никакой фильтрации по домену/расширению — только простая подстрока.
    """
    return [link for link in links if substring in link]
