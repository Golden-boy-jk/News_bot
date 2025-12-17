import pytest
from app.config import Settings, get_settings


@pytest.fixture
def fake_settings(monkeypatch):
    settings = Settings(
        telegram_bot_token="token",
        telegram_chat_id="chat_id",
        error_chat_id="error_chat_id",
        database_path=":memory:",
    )

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: settings,
    )

    return settings
