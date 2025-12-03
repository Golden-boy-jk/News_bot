# app/config.py
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    error_chat_id: str
    database_path: str = "news.db"

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID должны быть заданы в .env")

        error_chat_id = os.getenv("TELEGRAM_ERROR_CHAT_ID", chat_id)
        db_path = os.getenv("DATABASE_PATH", "news.db")

        return cls(
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            error_chat_id=error_chat_id,
            database_path=db_path,
        )


settings = Settings.from_env()
