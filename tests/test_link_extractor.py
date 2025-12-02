# tests/test_link_extractor.py
from typing import List
from types import SimpleNamespace

import pytest

from app.link_extractor import extract_links_from_url


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_extract_links_from_url_basic(monkeypatch):
    html = """
    <html>
      <head><title>Test</title></head>
      <body>
        <a href="https://example.com/abs">Absolute</a>
        <a href="/rel1">Relative 1</a>
        <a href="rel2">Relative 2</a>
        <a href="#anchor">Anchor only</a>
      </body>
    </html>
    """

    def fake_get(url: str, timeout: int = 10):
        assert url == "https://example.com"
        assert timeout == 10
        return DummyResponse(html)

    import app.link_extractor as le
    monkeypatch.setattr(le.requests, "get", fake_get)

    links: List[str] = extract_links_from_url("https://example.com")

    # Проверяем, что urljoin отработал
    assert "https://example.com/abs" in links
    assert "https://example.com/rel1" in links
    assert "https://example.com/rel2" in links
    # якорь превратится в base + "#anchor"
    assert "https://example.com#anchor" in links
    assert len(links) == 4


def test_extract_links_from_url_no_links(monkeypatch):
    html = "<html><body><p>No links here</p></body></html>"

    def fake_get(url: str, timeout: int = 10):
        return DummyResponse(html)

    import app.link_extractor as le
    monkeypatch.setattr(le.requests, "get", fake_get)

    links = extract_links_from_url("https://example.com")
    assert links == []


def test_extract_links_from_url_http_error(monkeypatch):
    def fake_get(url: str, timeout: int = 10):
        return DummyResponse("error", status_code=500)

    import app.link_extractor as le
    monkeypatch.setattr(le.requests, "get", fake_get)

    with pytest.raises(RuntimeError):
        extract_links_from_url("https://example.com")
