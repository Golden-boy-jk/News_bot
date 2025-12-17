# tests/test_error_notifier.py
def test_send_error_alert_success(fake_settings, monkeypatch, capsys):
    import app.error_notifier as en

    sent = {}

    class DummyBot:
        def __init__(self, token: str):
            sent["token"] = token

        def send_message(self, chat_id: str, text: str):
            sent["chat_id"] = chat_id
            sent["text"] = text

    class DummySettings:
        telegram_bot_token = "TEST_TOKEN"
        error_chat_id = "ERROR_CHAT"

    # подменяем зависимости внутри модуля
    monkeypatch.setattr(en, "Bot", DummyBot)
    monkeypatch.setattr(en, "get_settings", lambda: DummySettings)

    long_text = "X" * 10000
    en.send_error_alert(long_text)

    # проверяем, что бот получил корректные параметры
    assert sent["token"] == "TEST_TOKEN"
    assert sent["chat_id"] == "ERROR_CHAT"
    assert sent["text"].startswith("[ERROR][news-bot] ")
    assert len(sent["text"]) <= 4000

    captured = capsys.readouterr()
    assert "Ошибка отправки" not in captured.out
    assert "Ошибка отправки" not in captured.err


def test_send_error_alert_telegram_error(monkeypatch, capsys):
    """
    Ветка except: Bot.send_message выбрасывает TelegramError,
    мы его глотаем и печатаем сообщение.
    """
    import app.error_notifier as en

    class DummyError(Exception):
        pass

    class DummyBot:
        def __init__(self, token: str):
            self.token = token

        def send_message(self, chat_id: str, text: str):
            raise DummyError("fail to send")

    class DummySettings:
        telegram_bot_token = "TEST_TOKEN"
        error_chat_id = "ERROR_CHAT"

    monkeypatch.setattr(en, "TelegramError", DummyError)
    monkeypatch.setattr(en, "Bot", DummyBot)
    monkeypatch.setattr(en, "get_settings", lambda: DummySettings)

    en.send_error_alert("boom")

    captured = capsys.readouterr()
    assert "Ошибка отправки error-алерта в Telegram" in captured.out
