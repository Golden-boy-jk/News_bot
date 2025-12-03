# tests/test_link_extractor.py
import pytest
import requests

from app import link_extractor as le


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_extract_links_from_url_basic(monkeypatch):
    html = """
    <html>
      <body>
        <a href="https://example.com/a">A</a>
        <a href="/b">B</a>
        <a href="#anchor">Anchor</a>
      </body>
    </html>
    """

    def fake_get(url: str, timeout: int = 10):
        return DummyResponse(html)

    monkeypatch.setattr(le.requests, "get", fake_get)

    links = le.extract_links_from_url("https://example.com/root")

    assert "https://example.com/a" in links
    assert "https://example.com/b" in links
    assert "https://example.com/root#anchor" in links
    assert len(links) == 3


def test_extract_links_from_url_no_links(monkeypatch):
    html = "<html><body><p>No links here</p></body></html>"

    def fake_get(url: str, timeout: int = 10):
        return DummyResponse(html)

    monkeypatch.setattr(le.requests, "get", fake_get)

    links = le.extract_links_from_url("https://example.com")
    assert links == []


def test_extract_links_from_url_http_error(monkeypatch):
    def fake_get(url: str, timeout: int = 10):
        return DummyResponse("error", status_code=500)

    monkeypatch.setattr(le.requests, "get", fake_get)

    with pytest.raises(RuntimeError):
        le.extract_links_from_url("https://example.com")


def test_extract_links_from_url_retry_success(monkeypatch):
    """
    Первая попытка — сетевой эксепшен, вторая — успешная.
    Должны получить ссылки и 2 вызова requests.get.
    """
    html = "<html><body><a href=\"/ok\">OK</a></body></html>"
    calls = {"n": 0}

    def fake_get(url: str, timeout: int = 10):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("temporary")
        return DummyResponse(html)

    # убираем реальные sleep в тестах
    monkeypatch.setattr(le, "time", type("T", (), {"sleep": lambda *_: None})())
    monkeypatch.setattr(le.requests, "get", fake_get)

    links = le.extract_links_from_url("https://example.com")

    assert "https://example.com/ok" in links
    assert calls["n"] == 2


def test_fetch_html_with_retry_fail(monkeypatch):
    """
    Все попытки падают — должен быть RuntimeError.
    """
    def fake_get(url: str, timeout: int = 10):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(le.requests, "get", fake_get)
    monkeypatch.setattr(le, "time", type("T", (), {"sleep": lambda *_: None})())

    with pytest.raises(RuntimeError):
        le._fetch_html_with_retry("https://example.com", timeout=1, max_attempts=3)
