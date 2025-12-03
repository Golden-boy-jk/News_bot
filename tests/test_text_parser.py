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
