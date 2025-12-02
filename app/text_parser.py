# app/text_parser.py
from typing import Optional

import requests
from bs4 import BeautifulSoup


def fetch_text_content(url: str, timeout: int = 10) -> Optional[str]:
    """
    Скачивает HTML и возвращает текстовый контент:
    - достаёт <title> и вставляет первой строкой (если есть)
    - удаляет <script>, <style>, <noscript>
    - убирает HTML-теги
    """
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

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
    return cleaned or None
