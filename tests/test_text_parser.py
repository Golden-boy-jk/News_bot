# tests/test_text_parser.py
from types import SimpleNamespace
from typing import Optional

from app.text_parser import fetch_text_content


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_text_content_with_title_and_scripts(monkeypatch):
    html = """
    <html>
      <head>
        <title>My Page Title</title>
        <script>var x = 1;</script>
      </head>
      <body>
        <h1>Header</h1>
        <p>Some text</p>
        <style>body {color: red;}</style>
        <noscript>Enable JS</noscript>
      </body>
    </html>
    """

    def fake_get(url: str, timeout: int = 10):
        assert url == "https://example.com/page"
        assert timeout == 10
        return DummyResponse(html)

    import app.text_parser as tp
    monkeypatch.setattr(tp.requests, "get", fake_get)

    text: Optional[str] = fetch_text_content("https://example.com/page")
    assert text is not None

    lines = text.splitlines()
    # первая строка — title
    assert lines[0] == "My Page Title"
    # скрипты/стили/ noscript удалены
    concatenated = "\n".join(lines)
    assert "var x = 1" not in concatenated
    assert "body {color: red;}" not in concatenated
    assert "Enable JS" not in concatenated
    # основной текст остался
    assert "Header" in concatenated
    assert "Some text" in concatenated


def test_fetch_text_content_without_title(monkeypatch):
    html = """
    <html>
      <body>
        <h1>Header only</h1>
        <p>Some text</p>
      </body>
    </html>
    """

    def fake_get(url: str, timeout: int = 10):
        return DummyResponse(html)

    import app.text_parser as tp
    monkeypatch.setattr(tp.requests, "get", fake_get)

    text = fetch_text_content("https://example.com/no-title")
    assert text is not None

    lines = text.splitlines()
    # title отсутствовал, значит первая строка — Header only
    assert lines[0] == "Header only"
    assert "Some text" in text


def test_fetch_text_content_empty_result_returns_none(monkeypatch):
    # HTML без видимого текста
    html = "<html><head></head><body></body></html>"

    def fake_get(url: str, timeout: int = 10):
        return DummyResponse(html)

    import app.text_parser as tp
    monkeypatch.setattr(tp.requests, "get", fake_get)

    text = fetch_text_content("https://example.com/empty")
    # cleaned == "" → функция должна вернуть None
    assert text is None
