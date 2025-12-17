# app/error_notifier.py
from telegram import Bot
from telegram.error import TelegramError

from .config import get_settings


def send_error_alert(text: str) -> None:
    settings = get_settings()
    """
    Отправка алерта об ошибке в отдельный Telegram-чат/канал.
    """
    bot = Bot(token=settings.telegram_bot_token)
    msg = f"[ERROR][news-bot] {text}"
    try:
        bot.send_message(chat_id=settings.error_chat_id, text=msg[:4000])
    except TelegramError as e:
        # тут без рекурсии: просто молча игнорируем или логируем в stderr
        print(f"Ошибка отправки error-алерта в Telegram: {e}")
