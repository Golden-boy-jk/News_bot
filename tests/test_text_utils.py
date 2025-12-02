# tests/test_text_utils.py
from app.text_utils import truncate_message, TELEGRAM_LIMIT


def test_truncate_message_short_not_modified():
    text = "Короткое сообщение"
    result = truncate_message(text)
    assert result == text
    assert len(result) == len(text)


def test_truncate_message_long_is_truncated_and_with_suffix():
    # Делаем текст чуть длиннее лимита без пробелов и переносов
    text = "a" * (TELEGRAM_LIMIT + 200)
    result = truncate_message(text)

    assert len(result) <= TELEGRAM_LIMIT
    # проверяем, что есть пометка о сокращении
    assert "сокращено" in result or "сокращён" in result


def test_truncate_message_prefers_newline(monkeypatch):
    """
    Текст длиннее лимита, внутри есть перенос строки ближе к концу.
    Должна сработать ветка с last_newline и специальным суффиксом.
    """
    import app.text_utils as tu

    calls = []
    monkeypatch.setattr(tu, "log_warning", lambda msg: calls.append(msg))

    limit = 200
    # длина > limit, перенос строки попадает в диапазон (0.6 * safe_limit, safe_limit)
    text = "a" * 100 + "\n" + "b" * 200

    result = tu.truncate_message(text, limit=limit)

    assert len(result) <= limit
    assert "текст сокращён из-за лимита Telegram" in result
    # логгер предупреждения вызывался
    assert calls


def test_truncate_message_falls_back_to_space(monkeypatch):
    """
    Текст длиннее лимита, без переносов строки, но с пробелом ближе к концу.
    Должна сработать ветка с last_space и суффиксом '… (сокращено)'.
    """
    import app.text_utils as tu

    calls = []
    monkeypatch.setattr(tu, "log_warning", lambda msg: calls.append(msg))

    limit = 200
    # длина > limit, пробел попадает в диапазон (0.6 * safe_limit, safe_limit)
    text = "a" * 100 + " " + "b" * 200

    result = tu.truncate_message(text, limit=limit)

    assert len(result) <= limit
    assert "… (сокращено)" in result
    assert "текст сокращён из-за лимита Telegram" not in result
    assert calls
