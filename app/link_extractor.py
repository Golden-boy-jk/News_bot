# app/link_extractor.py
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def extract_links_from_url(url: str, timeout: int = 10) -> List[str]:
    """
    Скачивает HTML страницу и достаёт все <a href="..."> ссылки.
    Возвращает absolute URLs, без доп. фильтрации по домену/расширению.
    """
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Собираем абсолютную ссылку
        full_url = urljoin(url, href)
        links.append(full_url)

    return links
