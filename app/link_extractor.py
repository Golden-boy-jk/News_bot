# app/link_extractor.py
from typing import List
from urllib.parse import urljoin
import time

import requests
from requests import RequestException
from bs4 import BeautifulSoup


def _fetch_html_with_retry(url: str, timeout: int = 10, max_attempts: int = 3) -> str:
    """
    HTTP-запрос с простой retry-политикой:
    - до max_attempts попыток;
    - ретраим любые RequestException;
    - в случае неуспеха поднимаем RuntimeError (под это затачиваем тесты).
    """
    last_err: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except RequestException as exc:
            last_err = exc
            if attempt < max_attempts:
                # короткая пауза между попытками
                time.sleep(0.1)
            else:
                raise RuntimeError(f"Не удалось загрузить страницу {url}") from exc


def extract_links_from_url(url: str, timeout: int = 10) -> List[str]:
    """
    Скачивает HTML-страницу и достаёт все <a href="..."> ссылки.
    Возвращает список абсолютных URL-ов.

    При проблемах с HTTP бросает RuntimeError.
    """
    html = _fetch_html_with_retry(url, timeout=timeout)

    soup = BeautifulSoup(html, "lxml")

    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = urljoin(url, href)
        links.append(full_url)

    return links
