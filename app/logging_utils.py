# app/logging_utils.py
import logging
import sys

from .error_notifier import send_error_alert

logger = logging.getLogger("news_bot")


def setup_logging(level: int = logging.INFO) -> None:
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)


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
