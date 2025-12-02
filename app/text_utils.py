# app/text_utils.py

from .logging_utils import log_warning

TELEGRAM_LIMIT = 4096

def truncate_message(text: str, limit: int = TELEGRAM_LIMIT) -> str:
    """
    Универсальное ограничение длины текста под лимиты Telegram (4096 символов).
    Обрезает мягко, по границе слова/строки, если возможно.
    """
    if len(text) <= limit:
        return text

    log_warning(f"Сообщение превышает лимит {limit} символов. Будет обрезано.")

    # оставим небольшой запас, чтобы точно не вылететь за границу
    safe_limit = limit - 50
    cropped = text[:safe_limit]

    # если можно обрезать по ближайшему переводу строки — так и делаем
    last_newline = cropped.rfind("\n")
    if last_newline != -1 and last_newline > safe_limit * 0.6:
        return cropped[:last_newline] + "\n...\n(текст сокращён из-за лимита Telegram)"

    # иначе режем по последнему пробелу
    last_space = cropped.rfind(" ")
    if last_space != -1 and last_space > safe_limit * 0.6:
        return cropped[:last_space] + " … (сокращено)"

    # если ничего лучше — обрезаем жестко
    return cropped + " … (сокращено)"
