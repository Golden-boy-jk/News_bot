# app/logging_utils.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from .error_notifier import send_error_alert


logger = logging.getLogger("news_bot")


def _create_rotating_file_handler(
    filename: str,
    level: int,
    formatter: logging.Formatter,
    max_bytes_env: str,
    backup_count_env: str,
) -> RotatingFileHandler:
    """
    Вспомогательная функция для создания файлового ротируемого хендлера.
    Параметры размера/количества бэкапов можно переопределить через env.
    """
    max_bytes_default = 5 * 1024 * 1024  # 5 MB
    backup_count_default = 5

    max_bytes = int(os.getenv(max_bytes_env, max_bytes_default))
    backup_count = int(os.getenv(backup_count_env, backup_count_default))

    handler = RotatingFileHandler(
        filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def setup_logging(level: int = logging.INFO) -> None:
    """
    Базовая настройка логирования.

    - Всегда логируем в stdout (удобно для dev и Docker-логов).
    - Опционально добавляем файловые ротируемые хендлеры:
        * app.log  — INFO и выше
        * error.log — WARNING и выше
    - Включение файлового логирования управляется переменной:
        NEWS_BOT_FILE_LOGGING=1 (по умолчанию включено).
      Директория логов — NEWS_BOT_LOG_DIR (по умолчанию /var/log/news_bot).
    """
    logger.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Чистим старые хендлеры, чтобы при повторных вызовах не плодить их
    logger.handlers.clear()

    # 1) Всегда логируем в stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # 2) Файловое логирование — включается флагом окружения
    file_logging_enabled = os.getenv("NEWS_BOT_FILE_LOGGING", "1") == "1"
    if not file_logging_enabled:
        return

    log_dir = os.getenv("NEWS_BOT_LOG_DIR", "/var/log/news_bot")

    try:
        os.makedirs(log_dir, exist_ok=True)

        # Общие логи приложения (INFO и выше)
        app_log_path = os.path.join(log_dir, "app.log")
        app_file_handler = _create_rotating_file_handler(
            filename=app_log_path,
            level=logging.INFO,
            formatter=formatter,
            max_bytes_env="NEWS_BOT_APP_LOG_MAX_BYTES",
            backup_count_env="NEWS_BOT_APP_LOG_BACKUP_COUNT",
        )
        logger.addHandler(app_file_handler)

        # Ошибки и варнинги (WARNING и выше) — отдельный файл
        error_log_path = os.path.join(log_dir, "error.log")
        error_file_handler = _create_rotating_file_handler(
            filename=error_log_path,
            level=logging.WARNING,
            formatter=formatter,
            max_bytes_env="NEWS_BOT_ERROR_LOG_MAX_BYTES",
            backup_count_env="NEWS_BOT_ERROR_LOG_BACKUP_COUNT",
        )
        logger.addHandler(error_file_handler)

    except Exception as e:
        # В проде это лучше не игнорировать, но падать из-за логов нельзя.
        # Просто работаем только через stdout.
        print(f"[logging_utils] Не удалось настроить файловое логирование: {e}", file=sys.stderr)


def log_info(msg: str) -> None:
    logger.info(msg)


def log_warning(msg: str) -> None:
    logger.warning(msg)


def log_error(msg: str, alert: bool = False) -> None:
    logger.error(msg)
    if alert:
        # защищаемся от падения, если в алерте что-то пошло не так
        try:
            send_error_alert(msg)
        except Exception as e:
            logger.error(f"Не удалось отправить алерт в Telegram: {e}")
