from __future__ import annotations

import sys

from .config import get_settings
from .db import get_connection
from .logging_utils import log_error, log_info


def check_settings() -> bool:
    settings = get_settings()
    """
    Проверяем, что заданы TELEGRAM_* и DATABASE_PATH.
    Никаких запросов к Telegram, только валидация конфигурации.
    """
    ok = True

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        log_error("Healthcheck: TELEGRAM_* настройки не заданы.", alert=False)
        ok = False

    if not settings.database_path:
        log_error("Healthcheck: DATABASE_PATH не задан.", alert=False)
        ok = False

    return ok


def check_db() -> bool:
    settings = get_settings()
    """
    Простейшая проверка доступности БД:
    - устанавливаем соединение
    - выполняем SELECT 1
    """
    try:
        with get_connection(settings.database_path) as conn:
            conn.execute("SELECT 1;")
        return True
    except Exception as exc:  # noqa: BLE001
        log_error(f"Healthcheck: ошибка доступа к БД: {exc}", alert=False)
        return False


def main() -> int:
    """
    Возвращает 0, если всё ок, иначе 1.
    Это важно для Docker HEALTHCHECK.
    """
    ok_settings = check_settings()
    ok_db = check_db()

    if ok_settings and ok_db:
        log_info("Healthcheck: OK")
        return 0

    log_error("Healthcheck: FAILED", alert=False)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())  # pragma: no cover
