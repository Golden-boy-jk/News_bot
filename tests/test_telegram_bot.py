from types import SimpleNamespace

import app.telegram_bot as tb
from app.telegram_bot import (
    _safe_url,
    build_post_html,
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
        self.sent.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
        return SimpleNamespace(message_id=123)


class DummyBotError:
    def __init__(self, token: str):
        self.token = token

    def send_message(self, chat_id: str, text: str, parse_mode: str = None):
        from telegram.error import TelegramError

        raise TelegramError("fail")


def test_send_message_via_bot_success(monkeypatch):
    dummy_bot = DummyBotSuccess(token="TEST_TOKEN")

    msg_id = tb.send_message_via_bot(
        bot=dummy_bot,
        chat_id="12345",
        text="Hello, world!",
    )

    assert msg_id == "123"
    assert len(dummy_bot.sent) == 1
    sent = dummy_bot.sent[0]
    assert sent["chat_id"] == "12345"
    assert "Hello, world!" in sent["text"]
    assert sent["parse_mode"] == "HTML"


def test_send_message_via_bot_telegram_error_logs_and_returns_none(monkeypatch):
    dummy_bot = DummyBotError(token="TEST_TOKEN")

    logged = []

    def fake_log_error(msg: str, alert: bool = False):
        logged.append((msg, alert))

    monkeypatch.setattr(tb, "log_error", fake_log_error)

    result = tb.send_message_via_bot(
        bot=dummy_bot,
        chat_id="CHAT",
        text="Some text",
    )

    assert result is None
    assert logged

    msg, alert = logged[0]
    assert alert is True
    assert "Ошибка отправки сообщения в Telegram" in msg
    assert "fail" in msg


def test_send_message_via_bot_splits_long_text_into_multiple_messages(monkeypatch):
    dummy_bot = DummyBotSuccess(token="TEST_TOKEN")

    # чтобы truncate_message не отрезал
    monkeypatch.setattr(tb, "truncate_message", lambda x: x)

    long_text = "A" * (tb.TELEGRAM_MAX_LEN + 100)
    msg_id = tb.send_message_via_bot(
        bot=dummy_bot,
        chat_id="12345",
        text=long_text,
    )

    assert msg_id == "123"
    assert len(dummy_bot.sent) >= 2
    assert all(m["parse_mode"] == "HTML" for m in dummy_bot.sent)
    assert all(len(m["text"]) <= tb.TELEGRAM_MAX_LEN for m in dummy_bot.sent)


def test_format_tools_digest_message_structure_and_use_cases():
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

    # базовые блоки формата
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

    # ВАЖНО: юзкейсы реально попали в итоговый текст
    assert "Юзкейс: Автоматизация deploy." in msg
    assert "Юзкейс: Статический анализ кода." in msg


def test_format_weekly_digest_message_empty_events():
    msg = format_weekly_digest_message([])

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
    assert "Первая строка текста" in body
    assert "Вторая строка текста" in body


def test_format_news_message_structure():
    url = "https://openai.com/2025/test-news"
    content = "Новый релиз модели\nОчень важное обновление для разработчиков."

    msg = format_news_message(url=url, content=content, topic_tag="#AI", source_tag="#OpenAI")

    assert "💡 Что произошло:" in msg
    assert "📌 Почему это важно:" in msg
    assert "🔗 Источник:" in msg
    assert "😅 Юмор:" in msg
    assert url in msg
    assert "#AI" in msg
    assert "#OpenAI" in msg


def test_safe_url_escapes_quotes():
    assert _safe_url('https://ex.com/?q="x"&a=1') == "https://ex.com/?q=&quot;x&quot;&amp;a=1"


def test_build_post_html_escapes_source_url_with_quotes():
    # Этот тест ловит регрессию: если в build_post_html снова поставить _safe() вместо _safe_url()
    url = 'https://ex.com/?q="x"&a=1'
    msg = build_post_html(
        what="w",
        why="y",
        source_url=url,
        humor="h",
        hashtags="#t",
    )

    # В блоке "Источник" URL должен быть с экранированными кавычками и &
    assert "🔗 Источник:" in msg
    assert "&quot;x&quot;" in msg
    assert "&amp;a=1" in msg
