from app.filters import filter_link_by_substring


def test_filter_link_by_substring_basic():
    links = [
        "https://openai.com/blog/something",
        "https://openai.com/2025/awesome-news",
        "https://google.com/ai/2025/another-news",
        "https://example.com/2024/old-news",
    ]

    result = filter_link_by_substring(links, "/2025/")
    assert "https://openai.com/2025/awesome-news" in result
    assert "https://google.com/ai/2025/another-news" in result
    assert "https://openai.com/blog/something" not in result
    assert "https://example.com/2024/old-news" not in result


def test_filter_link_by_substring_empty():
    assert filter_link_by_substring([], "/2025/") == []
    assert filter_link_by_substring(["https://example.com"], "/2025/") == []
