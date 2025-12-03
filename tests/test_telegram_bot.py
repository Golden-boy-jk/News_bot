from types import SimpleNamespace

from app.telegram_bot import (
    format_news_message,
    format_tools_digest_message,
    format_weekly_digest_message,
    send_message,
    split_title_and_body,
)


class DummyBotSuccess:
    def __init__(self, token: str):
        self.token = token
        self.sent = []

    def send_message(self, chat_id: str, text: str, parse_mode: str = None):
        # сохраняем параметры отправки, чтобы можно было проверить
        self.sent.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
        # имитируем объект Message c полем message_id
        return SimpleNamespace(message_id=123)


class DummyBotError:
    def __init__(self, token: str):
        self.token = token

    def send_message(self, chat_id: str, text: str, parse_mode: str = None):
        from telegram.error import TelegramError

        raise TelegramError("fail")


def test_send_message_success(monkeypatch):
    # подменяем Bot на DummyBotSuccess
    import app.telegram_bot as tb

    dummy_bot = DummyBotSuccess(token="TEST_TOKEN")

    def fake_bot(token: str):
        assert token == "TEST_TOKEN"
        return dummy_bot

    monkeypatch.setattr(tb, "Bot", fake_bot)

    msg_id = send_message(
        bot_token="TEST_TOKEN",
        chat_id="12345",
        text="Hello, world!",
    )

    assert msg_id == "123"
    assert len(dummy_bot.sent) == 1
    sent = dummy_bot.sent[0]
    assert sent["chat_id"] == "12345"
    assert "Hello, world!" in sent["text"]
    assert sent["parse_mode"] == "Markdown"


def test_send_message_telegram_error_logs_and_returns_none(monkeypatch):
    import app.telegram_bot as tb

    # подменяем Bot на DummyBotError
    monkeypatch.setattr(tb, "Bot", lambda token: DummyBotError(token))

    logged = []

    def fake_log_error(msg: str, alert: bool = False):
        logged.append((msg, alert))

    monkeypatch.setattr(tb, "log_error", fake_log_error)

    result = send_message(
        bot_token="TOKEN",
        chat_id="CHAT",
        text="Some text",
    )

    assert result is None
    assert logged  # что-то залогировали
    assert logged[0][1] is True  # alert=True


def test_format_tools_digest_message_structure():
    tools = [
        {
            "title": "Tool A",
            "summary": "Helps with CI/CD.",
            "url": "https://example.com/tool-a",
            "use_case": "Автоматизация deploy.",
            "source_tag": "#DevTools",
        },
        {
            "title": "Tool B",
            "summary": "Improves code quality.",
            "url": "https://example.com/tool-b",
            "use_case": "Статический анализ кода.",
            "source_tag": "#Python",
        },
    ]

    msg = format_tools_digest_message(tools)

    # Проверяем наличие основных блоков формата
    assert "💡 Что произошло:" in msg
    assert "📌 Почему это важно:" in msg
    assert "🔗 Источник:" in msg
    assert "😅 Юмор:" in msg

    # Тулзы перечислены
    assert "Tool A" in msg
    assert "Tool B" in msg
    assert "https://example.com/tool-a" in msg
    assert "https://example.com/tool-b" in msg
    assert "#DevTools" in msg
    assert "#Python" in msg


def test_format_weekly_digest_message_empty_events():
    msg = format_weekly_digest_message([])

    # Фоллбек-сообщение без событий
    assert "громких новостей почти не было" in msg
    assert "💡 Что произошло:" in msg
    assert "📌 Почему это важно:" in msg
    assert "😅 Юмор:" in msg


def test_format_weekly_digest_message_with_events():
    events = [
        {
            "title": "Событие 1",
            "summary": "Важно для разработчиков.",
            "url": "https://example.com/event1",
            "source_tag": "#AI",
        }
    ]

    msg = format_weekly_digest_message(events)

    assert "Событие 1" in msg
    assert "Важно для разработчиков." in msg
    assert "https://example.com/event1" in msg
    assert "#AI" in msg
    assert "💡 Что произошло:" in msg
    assert "📌 Почему это важно:" in msg


def test_split_title_and_body_empty():
    title, body = split_title_and_body("")
    assert title == "Свежая новость из мира IT"
    assert body == ""


def test_split_title_and_body_basic():
    content = "Заголовок\nПервая строка текста\nВторая строка текста"
    title, body = split_title_and_body(content)

    assert title == "Заголовок"
    # тело — склеенные строки
    assert "Первая строка текста" in body
    assert "Вторая строка текста" in body


def test_format_news_message_structure():
    url = "https://openai.com/2025/test-news"
    content = "Новый релиз модели\nОчень важное обновление для разработчиков."

    msg = format_news_message(url=url, content=content, topic_tag="#AI", source_tag="#OpenAI")

    # проверяем наличие ключевых блоков
    assert "💡 Что произошло:" in msg
    assert "📌 Почему это важно:" in msg
    assert "🔗 Источник:" in msg
    assert "😅 Юмор:" in msg
    assert url in msg
    assert "#AI" in msg
    assert "#OpenAI" in msg
