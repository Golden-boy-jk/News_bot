# tests/test_text_parser.py
import pytest
import requests

from app import text_parser as tp


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


# --- общий мок переводчика, чтобы не ходить в сеть ---


@pytest.fixture(autouse=True)
def mock_google_translator(monkeypatch):
    """
    Во всех тестах подменяем GoogleTranslator так, чтобы он просто
    возвращал исходный текст и не делал внешних HTTP-запросов.
    """
    class DummyTranslator:
        def __init__(self, source="auto", target="ru"):
            pass

        def translate(self, text: str) -> str:
            return text

    monkeypatch.setattr(tp, "GoogleTranslator", DummyTranslator)


# --- тесты fetch_text_content ---


def test_fetch_text_content_basic(monkeypatch):
    html = """
    <html>
      <head>
        <title>My Title</title>
        <style>.cls { color: red; }</style>
      </head>
      <body>
        <p>First paragraph.</p>
        <script>console.log("noise")</script>
        <p>Second paragraph.</p>
      </body>
    </html>
    """

    def fake_get(url: str, timeout: int = 10):
        return DummyResponse(html)

    monkeypatch.setattr(tp.requests, "get", fake_get)

    content = tp.fetch_text_content("https://example.com")

    lines = content.splitlines()
    assert lines[0] == "My Title"
    assert "noise" not in content
    assert "First paragraph." in content
    assert "Second paragraph." in content


def test_fetch_text_content_no_title(monkeypatch):
    html = """
    <html>
      <body>
        <p>Only content</p>
      </body>
    </html>
    """

    def fake_get(url: str, timeout: int = 10):
        return DummyResponse(html)

    monkeypatch.setattr(tp.requests, "get", fake_get)

    content = tp.fetch_text_content("https://example.com")
    assert "Only content" in content
    # заголовок не должен появиться как отдельная строка
    assert "My Title" not in content


def test_fetch_text_content_http_error(monkeypatch):
    def fake_get(url: str, timeout: int = 10):
        return DummyResponse("error", status_code=500)

    monkeypatch.setattr(tp.requests, "get", fake_get)
    monkeypatch.setattr(tp, "time", type("T", (), {"sleep": lambda *_: None})())

    with pytest.raises(RuntimeError):
        tp.fetch_text_content("https://example.com")


def test_fetch_text_content_retry_success(monkeypatch):
    """
    Первая попытка падает (ConnectionError), вторая — успешная.
    Должен сработать retry.
    """
    html = "<html><body><p>OK</p></body></html>"
    calls = {"n": 0}

    def fake_get(url: str, timeout: int = 10):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("temporary")
        return DummyResponse(html)

    monkeypatch.setattr(tp.requests, "get", fake_get)
    monkeypatch.setattr(tp, "time", type("T", (), {"sleep": lambda *_: None})())

    content = tp.fetch_text_content("https://example.com")
    assert "OK" in content
    assert calls["n"] == 2


def test_fetch_text_content_inserts_title_if_missing_in_lines(monkeypatch):
    """
    Если <title> есть, но get_text не возвращает его первой строкой,
    функция должна вставить заголовок в начало вручную.
    """
    html = "<html><head><title>My Title</title></head><body>Body only</body></html>"

    # 1) Не ходим в сеть
    monkeypatch.setattr(tp, "_download_with_retry", lambda url, timeout=10: html)

    # 2) Фейковый BeautifulSoup
    class FakeSoup:
        def __init__(self, html_text, parser):
            self.title = type("T", (), {"string": "My Title"})()

        def __call__(self, names):
            return []

        def get_text(self, separator="\n", strip=True):
            # Текст без заголовка — чтобы условие lines[0] != title_text выполнилось
            return "Body only"

    monkeypatch.setattr(tp, "BeautifulSoup", FakeSoup)

    content = tp.fetch_text_content("https://example.com/title-insert")
    lines = content.splitlines()

    assert lines[0] == "My Title"
    assert "Body only" in content


def test_fetch_text_content_returns_none_for_empty_text(monkeypatch):
    """
    HTML после очистки не содержит видимого текста — функция должна вернуть None.
    """
    html = """
    <html>
      <body>
        <script>console.log("only script")</script>
        <style>.cls { color: red; }</style>
        <noscript>fallback</noscript>
      </body>
    </html>
    """

    monkeypatch.setattr(tp, "_download_with_retry", lambda url, timeout=10: html)

    content = tp.fetch_text_content("https://example.com/empty")
    assert content is None


# --- тесты retry-хелпера ---


def test_download_with_retry_fail(monkeypatch):
    """
    Все попытки падают — должен быть RuntimeError из _download_with_retry.
    """
    def fake_get(url: str, timeout: int = 10):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(tp.requests, "get", fake_get)
    monkeypatch.setattr(tp, "time", type("T", (), {"sleep": lambda *_: None})())

    with pytest.raises(RuntimeError):
        tp._download_with_retry("https://example.com", timeout=1, max_attempts=3)


# --- покрываем обе ветки translate_to_ru ---


def test_translate_to_ru_ok_path(monkeypatch):
    """
    Успешный путь: GoogleTranslator возвращает текст, try-ветка выполняется.
    """
    class DummyTranslator:
        def __init__(self, source="auto", target="ru"):
            pass

        def translate(self, text: str) -> str:
            return text + " RU"

    monkeypatch.setattr(tp, "GoogleTranslator", DummyTranslator)

    result = tp.translate_to_ru("hello")
    assert result == "hello RU"


def test_translate_to_ru_exception_path(monkeypatch):
    """
    Ошибочный путь: GoogleTranslator кидает исключение — срабатывает except.
    """
    class FailingTranslator:
        def __init__(self, source="auto", target="ru"):
            pass

        def translate(self, text: str) -> str:
            raise RuntimeError("boom")

    monkeypatch.setattr(tp, "GoogleTranslator", FailingTranslator)

    result = tp.translate_to_ru("hello")
    assert result == "hello"


# --- тест, который прогоняет полный пайплайн очистки ---


def test_full_clean_pipeline(monkeypatch):
    """
    Проверяет, что полная цепочка обработки (clean_unicode, нормализация пробелов,
    translate_to_ru) реально выполняется.
    """
    html = """
    <html>
      <head><title>Test Title</title></head>
      <body>
        <p>Line\u200bwith\u200dmessy\u200fchars</p>
        <p>Another   line</p>
      </body>
    </html>
    """

    # мокаем скачивание
    monkeypatch.setattr(tp, "_download_with_retry", lambda url, timeout=10: html)

    # переводчик уже замокан фикстурой mock_google_translator → вернёт исходный текст
    content = tp.fetch_text_content("https://example.com/full")

    # Заголовок на месте
    assert "Test Title" in content
    # Мусорные юникод-символы очищены
    assert "\u200b" not in content
    assert "\u200d" not in content
    assert "\u200f" not in content
    # Полезный текст остался
    assert "Line" in content
    assert "messy" in content
    assert "Another line" in content


def test_protect_tech_terms():
    from app.text_parser import _protect_tech_terms

    text = "Python API CVE Zero-Day test something"
    protected, placeholders = _protect_tech_terms(text)

    # Должны появиться плейсхолдеры
    assert "__TECH_TERM_" in protected
    # все термины заменены плейсхолдерами
    for term in ["Python", "API", "CVE", "Zero-Day"]:
        assert term not in protected

    # Плейсхолдеры записаны
    assert len(placeholders) == 4


def test_restore_tech_terms():
    from app.text_parser import _restore_tech_terms

    text = "Hello __TECH_TERM_0__ world"
    placeholders = {"__TECH_TERM_0__": "Python"}

    restored = _restore_tech_terms(text, placeholders)

    assert restored == "Hello Python world"


def test_translate_to_ru_keeps_tech_terms(monkeypatch):
    """
    Проверяет, что Python/API/CVE/Zero-Day остаются неизменными,
    даже если переводчик срабатывает.
    """
    from app import text_parser as tp

    class FakeTranslator:
        def __init__(self, source="auto", target="ru"):
            pass

        def translate(self, text):
            # имитируем перевод: все остальное переводим в «ТЕКСТ»
            return text.replace("something", "что-то")

    monkeypatch.setattr(tp, "GoogleTranslator", FakeTranslator)

    result = tp.translate_to_ru("Python API CVE Zero-Day something")

    # Тех-термины должны остаться
    assert "Python" in result
    assert "API" in result
    assert "CVE" in result
    assert "Zero-Day" in result

    # А остальной текст переведён
    assert "что-то" in result
