# test_news_professor.py
from typing import List

from app.news_professor import (
    NewsProfessor,
    get_today_tags,
    guess_source_from_url,
    split_title_and_summary,
    build_tool_use_case,
)


def test_split_title_and_summary_normal_and_empty():
    content = "Заголовок\nПервая строка\nВторая строка\nТретья строка\nЧетвертая строка"
    title, summary = split_title_and_summary(content)

    assert title == "Заголовок"
    assert "Первая строка" in summary
    assert "Вторая строка" in summary

    empty_title, empty_summary = split_title_and_summary("")
    assert empty_title is None
    assert empty_summary is None


def test_build_tool_use_case_variants():
    uc_github = build_tool_use_case("github_blog")
    uc_vscode = build_tool_use_case("vscode_updates")
    uc_docker = build_tool_use_case("docker_blog")
    uc_python = build_tool_use_case("python_org")
    uc_other = build_tool_use_case("some_other_source")

    assert "GitHub" in uc_github
    assert "VS Code" in uc_vscode or "кодинга" in uc_vscode
    assert "Docker" in uc_docker
    assert "Python" in uc_python
    assert uc_other != uc_github
    assert uc_other != uc_vscode
    assert uc_other != uc_docker


def test_get_today_tags_uses_weekday(monkeypatch):
    import app.news_professor as np

    class DummyDateTime:
        @classmethod
        def now(cls):
            class D:
                def weekday(self_nonlocal):
                    return 1  # Вторник
            return D()

    monkeypatch.setattr(np, "datetime", DummyDateTime)

    tags = get_today_tags()
    assert tags["topic_tag"] == "#Python"
    assert tags["source_tag"] == "#Разработка"


def test_collect_links_happy_and_error(monkeypatch):
    import app.news_professor as np

    collected_sites = []
    logs_error = []

    def fake_extract_links(url: str) -> List[str]:
        collected_sites.append(url)
        if "ok" in url:
            return [f"{url}/a1", f"{url}/a2"]
        else:
            raise RuntimeError("boom")

    def fake_log_info(msg: str):
        # просто заглушка
        pass

    def fake_log_error(msg: str, alert: bool = False):
        logs_error.append((msg, alert))

    monkeypatch.setattr(np, "init_db", lambda db_path: None)
    monkeypatch.setattr(np, "extract_links_from_url", fake_extract_links)
    monkeypatch.setattr(np, "log_info", fake_log_info)
    monkeypatch.setattr(np, "log_error", fake_log_error)

    prof = NewsProfessor(db_path=":memory:")
    sites = ["https://good.ok", "https://bad.fail"]

    links = prof.collect_links(sites)

    assert links == ["https://good.ok/a1", "https://good.ok/a2"]
    assert len(logs_error) == 1
    assert logs_error[0][1] is True  # alert=True


def test_fetch_and_store_new_articles_batch_happy_path(monkeypatch, tmp_path):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    links = [
        "https://site.com/2024/old",
        "https://site.com/2025/existing",
        "https://site.com/2025/new-tool",
        "https://site.com/2025/empty",
    ]

    def fake_link_exists(db_path: str, url: str) -> bool:
        return "existing" in url

    def fake_fetch_text(url: str):
        if "empty" in url:
            return None
        return f"Title for {url}\nSummary line\nBody text"

    saved = []

    def fake_save_news(db_path: str, url: str, title: str, summary: str,
                       content: str, source: str, score: float) -> None:
        saved.append(
            {
                "db_path": db_path,
                "url": url,
                "title": title,
                "summary": summary,
                "content": content,
                "source": source,
                "score": score,
            }
        )

    def fake_scores(texts: List[str]) -> List[float]:
        assert len(texts) == 1  # только new-tool
        return [0.7]

    monkeypatch.setattr(np, "filter_link_by_substring",
                        lambda links, substring: [l for l in links if substring in l])
    monkeypatch.setattr(np, "link_exists", fake_link_exists)
    monkeypatch.setattr(np, "fetch_text_content", fake_fetch_text)
    monkeypatch.setattr(np, "save_news", fake_save_news)
    monkeypatch.setattr(np, "compute_tfidf_scores", fake_scores)
    monkeypatch.setattr(np, "log_info", lambda msg: None)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))

    new_urls = prof.fetch_and_store_new_articles_batch(
        links=links,
        substring="/2025/",
        max_to_fetch=10,
    )

    assert new_urls == ["https://site.com/2025/new-tool"]
    assert len(saved) == 1
    rec = saved[0]
    assert rec["url"] == "https://site.com/2025/new-tool"
    assert rec["score"] == 0.7
    assert "Title for https://site.com/2025/new-tool" in rec["title"]


def test_publish_top_news_sorts_and_sends(monkeypatch, tmp_path):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    rows = [
        ("https://u1", "T1", "S1", "C1", "other", 0.5),
        ("https://u2", "T2", "S2", "C2", "openai", 2.0),
    ]

    def fake_get_news_by_urls(db_path: str, urls: List[str]):
        assert urls == ["https://u1", "https://u2"]
        return rows

    monkeypatch.setattr(np, "get_news_by_urls", fake_get_news_by_urls)
    monkeypatch.setattr(np, "get_today_tags",
                        lambda: {"topic_tag": "#TOPIC", "source_tag": "#DEFAULT"})

    formatted_calls = []
    sent_messages = []

    def fake_format_news_message(url: str, content: str, topic_tag: str, source_tag: str) -> str:
        formatted_calls.append(
            {
                "url": url,
                "content": content,
                "topic_tag": topic_tag,
                "source_tag": source_tag,
            }
        )
        return f"MSG:{url}"

    class DummySettings:
        telegram_bot_token = "TOKEN"
        telegram_chat_id = "CHAT"

    def fake_send_message(bot_token: str, chat_id: str, text: str):
        sent_messages.append({"token": bot_token, "chat_id": chat_id, "text": text})

    monkeypatch.setattr(np, "format_news_message", fake_format_news_message)
    monkeypatch.setattr(np, "send_message", fake_send_message)
    monkeypatch.setattr(np, "settings", DummySettings)
    monkeypatch.setattr(np, "log_info", lambda msg: None)
    monkeypatch.setattr(np, "log_warning", lambda msg: None)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))
    prof.publish_top_news(["https://u1", "https://u2"], max_to_publish=5)

    # порядок по score: сначала u2 (2.0), потом u1 (0.5)
    assert [m["url"] for m in formatted_calls] == ["https://u2", "https://u1"]
    assert all(m["topic_tag"] == "#TOPIC" for m in formatted_calls)

    tags_by_url = {m["url"]: m["source_tag"] for m in formatted_calls}
    assert tags_by_url["https://u2"] == "#AI"      # openai → #AI
    assert tags_by_url["https://u1"] == "#DEFAULT"  # other → дефолтный тег

    assert len(sent_messages) == 2
    assert all(m["token"] == "TOKEN" and m["chat_id"] == "CHAT" for m in sent_messages)


def test_build_tools_digest_items_basic(monkeypatch, tmp_path):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    rows = [
        ("https://tool1", "Tool 1", "Desc 1", "Content 1", "github_blog", 0.5),
        ("https://tool2", "Tool 2", "Desc 2", "Content 2", "docker_blog", 2.0),
        ("https://tool3", "Tool 3", "Desc 3", "Content 3", "other", 1.0),
    ]

    def fake_get_news_by_urls(db_path: str, urls: List[str]):
        return rows

    monkeypatch.setattr(np, "get_news_by_urls", fake_get_news_by_urls)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))

    items = prof.build_tools_digest_items(
        new_urls=[r[0] for r in rows],
        max_tools=2,
    )

    # Топ-2 по score: tool2 (2.0) и tool3 (1.0)
    assert [it["url"] for it in items] == ["https://tool2", "https://tool3"]

    for it in items:
        assert "use_case" in it
        assert "source_tag" in it

    devtools_urls = [it["url"] for it in items if it["source_tag"] == "#DevTools"]
    assert "https://tool2" in devtools_urls


def test_build_weekly_digest_items_basic(monkeypatch, tmp_path):
    import app.news_professor as np
    from app import db as db_module

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    rows = [
        ("https://ai", "AI News", "S1", "C1", "openai", 2.0, "2025-01-01T00:00:00"),
        ("https://py", "Py News", "S2", "C2", "python_org", 1.5, "2025-01-02T00:00:00"),
        ("https://other", "Other", "S3", "C3", "other", 0.5, "2025-01-03T00:00:00"),
    ]

    def fake_get_top_news_for_period(db_path: str, days_back: int, limit: int):
        return rows

    monkeypatch.setattr(db_module, "get_top_news_for_period", fake_get_top_news_for_period)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))
    items = prof.build_weekly_digest_items(days_back=7, limit=5)

    assert [it["url"] for it in items] == ["https://ai", "https://py", "https://other"]

    tags = {it["url"]: it["source_tag"] for it in items}
    assert tags["https://ai"] == "#AI"
    assert tags["https://py"] == "#Python"
    assert tags["https://other"] == "#НовостиIT"


def test_guess_source_from_url_all_sources():
    from app import news_professor as np

    cases = [
        ("https://www.anthropic.com/news", "anthropic"),
        ("https://huggingface.co/blog/awesome", "huggingface"),
        ("https://stability.ai/news", "stability_ai"),
        ("https://www.python.org/blogs/", "python_org"),
        ("https://realpython.com/", "realpython"),
        ("https://blog.jetbrains.com/pycharm/whats-new", "pycharm_blog"),
        ("https://www.pythonweekly.com/", "python_weekly"),
        ("https://www.databricks.com/blog", "databricks"),
        ("https://www.confluent.io/blog/", "confluent"),
        ("https://aws.amazon.com/blogs/big-data/some-post", "aws_bigdata"),
        ("https://thehackernews.com/some-article", "the_hacker_news"),
        ("https://gbhackers.com/post", "gbhackers"),
        ("https://cybersecuritynews.com/post", "cybersecuritynews"),
        ("https://code.visualstudio.com/updates/version", "vscode_updates"),
        ("https://www.docker.com/blog/something", "docker_blog"),
        ("https://openai.com/blog", "openai"),
        ("https://blog.google/technology/ai/post", "google_ai_blog"),
        ("https://github.blog/some-post", "github_blog"),
        ("https://www.anthropic.com/news", "anthropic"),
        ("https://huggingface.co/blog/awesome", "huggingface"),
    ]

    for url, expected in cases:
        assert np.guess_source_from_url(url) == expected


def test_build_tool_use_case_data_eng():
    # Добиваем ветку для databricks/confluent/aws_bigdata
    text = build_tool_use_case("databricks")
    assert "data-пайплайнами" in text or "больших данных" in text
