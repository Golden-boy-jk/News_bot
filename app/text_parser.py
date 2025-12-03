# app/text_parser.py
from typing import Optional
import time

import requests
from requests import RequestException
from bs4 import BeautifulSoup


def _download_with_retry(url: str, timeout: int = 10, max_attempts: int = 3) -> str:
    """
    HTTP-запрос с retry:
    - до max_attempts попыток;
    - ловим любые RequestException;
    - между попытками делаем небольшую паузу;
    - на последней неудачной попытке бросаем RuntimeError.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except RequestException as exc:
            if attempt < max_attempts:
                # в тестах мы мокаем time.sleep, так что здесь это дёшево
                time.sleep(0.1)
            else:
                # последняя попытка — пробовали всё, падаем
                raise RuntimeError(f"Не удалось загрузить контент {url}") from exc


def fetch_text_content(url: str, timeout: int = 10) -> Optional[str]:
    """
    Скачивает HTML и возвращает текстовый контент:
    - достаёт <title> и вставляет первой строкой (если есть);
    - удаляет <script>, <style>, <noscript>;
    - возвращает текст без HTML-тегов;
    - при HTTP-проблемах бросает RuntimeError.
    """
    html = _download_with_retry(url, timeout=timeout)

    soup = BeautifulSoup(html, "lxml")

    # title
    title_text = ""
    if soup.title and soup.title.string:
        title_text = soup.title.string.strip()

    # Удаляем шум
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if title_text:
        # вставляем заголовок в начало, если он не дублируется
        if not lines or lines[0] != title_text:
            lines.insert(0, title_text)

    cleaned = "\n".join(lines)
    return cleaned or None # pragma: no cover
