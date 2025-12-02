from app.text_utils import truncate_message, TELEGRAM_LIMIT


def test_truncate_message_short_not_modified():
    text = "Короткое сообщение"
    result = truncate_message(text)
    assert result == text
    assert len(result) == len(text)


def test_truncate_message_long_is_truncated_and_with_suffix():
    # Делаем текст чуть длиннее лимита
    text = "a" * (TELEGRAM_LIMIT + 200)
    result = truncate_message(text)

    assert len(result) <= TELEGRAM_LIMIT
    # проверяем, что есть пометка о сокращении
    assert "сокращено" in result or "сокращён" in result
