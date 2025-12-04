# app/text_parser.py
from typing import Optional
import time
import re

import requests
from requests import RequestException
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator


# Удаляем невидимые/мусорные unicode-символы
CLEAN_PATTERN = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f"        # Zero-width chars
    r"\ufeff"                                 # BOM
    r"\uf0b7\uf02d\uf0a7\uf0fc"               # Bullet-like private-use chars
    r"\xa0"                                   # non-breaking space
    r"]+"
)


def clean_unicode(text: str) -> str:
    return CLEAN_PATTERN.sub(" ", text)


# --- защита технических терминов от перевода --- #

TECH_TERM_PATTERNS = [
    re.compile(r"\bPython\b", re.IGNORECASE),
    re.compile(r"\bAPI\b", re.IGNORECASE),
    re.compile(r"\bCVE\b", re.IGNORECASE),
    re.compile(r"\bZero[-\s]?Day\b", re.IGNORECASE),
    re.compile(r"\bDocker\b", re.IGNORECASE),
    re.compile(r"\bKafka\b", re.IGNORECASE),
    re.compile(r"\bSpark\b", re.IGNORECASE),
    re.compile(r"\bAirflow\b", re.IGNORECASE),
    re.compile(r"\betc\b", re.IGNORECASE),
    # при желании сюда легко добавить Docker, Kafka, etc.
]


def _protect_tech_terms(text: str) -> tuple[str, dict[str, str]]:
    """
    Заменяет технические термины плейсхолдерами, чтобы переводчик их не трогал.
    Возвращает (новый_текст, словарь {плейсхолдер -> исходное_слово}).
    """
    placeholders: dict[str, str] = {}
    counter = 0

    def make_repl():
        nonlocal counter

        def _repl(match: re.Match) -> str:
            nonlocal counter
            placeholder = f"__TECH_TERM_{counter}__"
            counter += 1
            placeholders[placeholder] = match.group(0)
            return placeholder

        return _repl

    for pattern in TECH_TERM_PATTERNS:
        text = pattern.sub(make_repl(), text)

    return text, placeholders


def _restore_tech_terms(text: str, placeholders: dict[str, str]) -> str:
    """
    Возвращает плейсхолдеры обратно в исходные термины.
    """
    for placeholder, original in placeholders.items():
        text = text.replace(placeholder, original)
    return text


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


def translate_to_ru(text: str) -> str:
    """
    Перевод текста на русский язык.
    Технические термины (Python, API, CVE, Zero-Day и т.п.) оставляем без перевода.
    Если переводчик недоступен — возвращаем оригинал.
    """
    # пустые строки не трогаем
    if not text.strip():
        return text

    protected_text, placeholders = _protect_tech_terms(text)

    try:
        translated = GoogleTranslator(source="auto", target="ru").translate(protected_text)
    except Exception:
        # если deep_translator отвалился — безопасно вернуть исходный текст
        return text

    translated = _restore_tech_terms(translated, placeholders)
    return translated


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
        if not lines or lines[0] != title_text:
            lines.insert(0, title_text)

    cleaned = "\n".join(lines)
    cleaned = clean_unicode(cleaned)

    # нормализуем двойные пробелы и обрезаем края
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    cleaned = translate_to_ru(cleaned)
    return cleaned or None

