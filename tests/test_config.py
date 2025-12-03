# tests/test_config.py
import pytest

from app import config as cfg


def test_settings_from_env_missing_vars_raises(monkeypatch):
    """
    Покрываем ветку:
        if not token or not chat_id: raise RuntimeError(...)

    Удаляем TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID из окружения
    и убеждаемся, что Settings.from_env поднимает RuntimeError.
    """
    # гарантированно убираем переменные окружения внутри теста
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(RuntimeError):
        cfg.Settings.from_env()
