from app.telegram_bot import split_title_and_body, format_news_message


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
