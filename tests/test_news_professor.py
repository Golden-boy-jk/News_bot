# test_news_professor.py
from typing import List, Optional

import pytest

from app.news_professor import (
    NewsProfessor,
    get_today_tags,
    guess_source_from_url,
    split_title_and_summary,
    build_tool_use_case,
)


def test_guess_source_from_url_all_sources():
    from app import news_professor as np

    cases = [
        ("https://openai.com/blog", "openai"),
        ("https://blog.google/technology/ai/post", "google_ai_blog"),
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
        ("https://github.blog/some-post", "github_blog"),
        ("https://code.visualstudio.com/updates/version", "vscode_updates"),
        ("https://www.docker.com/blog/something", "docker_blog"),
        ("https://unknown-site.test/article", "other"),
    ]

    for url, expected in cases:
        assert np.guess_source_from_url(url) == expected


def test_build_tool_use_case_variants_and_data_eng():
    uc_github = build_tool_use_case("github_blog")
    uc_vscode = build_tool_use_case("vscode_updates")
    uc_docker = build_tool_use_case("docker_blog")
    uc_python = build_tool_use_case("python_org")
    uc_data_eng = build_tool_use_case("databricks")
    uc_other = build_tool_use_case("some_other_source")

    assert "GitHub" in uc_github
    assert "VS Code" in uc_vscode or "кодинга" in uc_vscode
    assert "Docker" in uc_docker
    assert "Python" in uc_python
    assert "data" in uc_data_eng or "данных" in uc_data_eng
    assert uc_other not in {uc_github, uc_vscode, uc_docker, uc_python, uc_data_eng}


def test_split_title_and_summary_normal_and_empty():
    content = "Заголовок\nПервая строка\nВторая строка\nТретья строка\nЧетвертая строка"
    title, summary = split_title_and_summary(content)

    assert title == "Заголовок"
    assert "Первая строка" in summary
    assert "Вторая строка" in summary

    empty_title, empty_summary = split_title_and_summary("")
    assert empty_title is None
    assert empty_summary is None


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

    def fake_fetch_text(url: str) -> Optional[str]:
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
    monkeypatch.setattr(np, "log_error", lambda msg, alert=False: None)

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


def test_fetch_and_store_respects_max_to_fetch(monkeypatch, tmp_path):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    links = [f"https://site.com/2025/new-{i}" for i in range(3)]

    def fake_filter(links_in, substring):
        return links_in

    def fake_link_exists(db_path, url):
        return False

    fetch_calls = []

    def fake_fetch(url):
        fetch_calls.append(url)
        return f"Title\nSummary\nBody for {url}"

    def fake_scores(texts: List[str]) -> List[float]:
        return [1.0] * len(texts)

    monkeypatch.setattr(np, "filter_link_by_substring", fake_filter)
    monkeypatch.setattr(np, "link_exists", fake_link_exists)
    monkeypatch.setattr(np, "fetch_text_content", fake_fetch)
    monkeypatch.setattr(np, "compute_tfidf_scores", fake_scores)
    monkeypatch.setattr(np, "save_news", lambda *a, **k: None)
    monkeypatch.setattr(np, "log_info", lambda msg: None)
    monkeypatch.setattr(np, "log_error", lambda msg, alert=False: None)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))

    new_urls = prof.fetch_and_store_new_articles_batch(
        links=links,
        substring="/2025/",
        max_to_fetch=2,
    )

    assert len(new_urls) == 2
    assert len(fetch_calls) == 2  # третью ссылку не парсим из-за break


def test_fetch_and_store_handles_exception_and_no_articles(monkeypatch, tmp_path):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    def fake_filter(links_in, substring):
        return ["https://badsite.com/err"]

    def fake_link_exists(db_path, url):
        return False

    def fake_fetch(url):
        raise RuntimeError("boom")

    errors = []
    infos = []

    monkeypatch.setattr(np, "filter_link_by_substring", fake_filter)
    monkeypatch.setattr(np, "link_exists", fake_link_exists)
    monkeypatch.setattr(np, "fetch_text_content", fake_fetch)
    monkeypatch.setattr(np, "compute_tfidf_scores", lambda texts: [])
    monkeypatch.setattr(np, "save_news", lambda *a, **k: None)
    monkeypatch.setattr(np, "log_error", lambda msg, alert=False: errors.append(msg))
    monkeypatch.setattr(np, "log_info", lambda msg: infos.append(msg))

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))

    new_urls = prof.fetch_and_store_new_articles_batch(
        links=["https://badsite.com/err"],
        substring="/2025/",
        max_to_fetch=5,
    )

    assert new_urls == []
    assert errors  # был лог ошибки парсинга
    assert any("Новых статей для сохранения нет." in m for m in infos)


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

    assert [m["url"] for m in formatted_calls] == ["https://u2", "https://u1"]
    tags_by_url = {m["url"]: m["source_tag"] for m in formatted_calls}
    assert tags_by_url["https://u2"] == "#AI"
    assert tags_by_url["https://u1"] == "#DEFAULT"
    assert len(sent_messages) == 2


def test_publish_top_news_no_new_urls(monkeypatch):
    import app.news_professor as np

    infos = []
    monkeypatch.setattr(np, "init_db", lambda db_path: None)
    monkeypatch.setattr(np, "log_info", lambda msg: infos.append(msg))

    monkeypatch.setattr(
        np,
        "get_news_by_urls",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("get_news_by_urls should not be called")
        ),
    )

    prof = NewsProfessor(db_path=":memory:")
    prof.publish_top_news([], max_to_publish=5)

    assert any("публиковать нечего" in m for m in infos)


def test_publish_top_news_no_rows(monkeypatch):
    import app.news_professor as np

    warns = []
    monkeypatch.setattr(np, "init_db", lambda db_path: None)
    monkeypatch.setattr(np, "get_news_by_urls", lambda *a, **k: [])
    monkeypatch.setattr(np, "log_warning", lambda msg: warns.append(msg))

    prof = NewsProfessor(db_path=":memory:")
    prof.publish_top_news(["https://u1"], max_to_publish=5)

    assert any("вернул пустой результат" in m for m in warns)


def test_publish_top_news_source_tags_all_topics(monkeypatch, tmp_path):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    rows = [
        ("https://ai", "T", "S", "C", "openai", 3.0),
        ("https://py", "T", "S", "C", "python_org", 2.0),
        ("https://de", "T", "S", "C", "databricks", 1.5),
        ("https://sec", "T", "S", "C", "the_hacker_news", 1.0),
        ("https://dev", "T", "S", "C", "github_blog", 0.5),
    ]

    monkeypatch.setattr(np, "get_news_by_urls", lambda db_path, urls: rows)
    monkeypatch.setattr(np, "get_today_tags",
                        lambda: {"topic_tag": "#TOP", "source_tag": "#DEF"})

    formatted = []

    def fake_format(url, content, topic_tag, source_tag):
        formatted.append({"url": url, "source_tag": source_tag, "topic_tag": topic_tag})
        return f"MSG:{url}"

    sent = []

    monkeypatch.setattr(np, "format_news_message", fake_format)
    monkeypatch.setattr(np, "send_message",
                        lambda bot_token, chat_id, text: sent.append(text))
    monkeypatch.setattr(np, "settings",
                        type("S", (), {"telegram_bot_token": "T", "telegram_chat_id": "C"}))
    monkeypatch.setattr(np, "log_info", lambda msg: None)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))
    prof.publish_top_news([r[0] for r in rows], max_to_publish=10)

    tags = {f["url"]: f["source_tag"] for f in formatted}
    assert tags["https://ai"] == "#AI"
    assert tags["https://py"] == "#Python"
    assert tags["https://de"] == "#DataEngineering"
    assert tags["https://sec"] == "#Security"
    assert tags["https://dev"] == "#DevTools"


def test_build_tools_digest_items_empty(monkeypatch, tmp_path):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))

    assert prof.build_tools_digest_items([], max_tools=5) == []

    monkeypatch.setattr(np, "get_news_by_urls", lambda *a, **k: [])
    assert prof.build_tools_digest_items(["https://tool"], max_tools=5) == []


def test_build_tools_digest_items_source_tags(monkeypatch, tmp_path):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    rows = [
        ("https://tool1", "Tool 1", "Desc 1", "Content 1", "github_blog", 0.5),
        ("https://tool2", "Tool 2", "Desc 2", "Content 2", "python_org", 2.0),
        ("https://tool3", "Tool 3", "Desc 3", "Content 3", "other", 1.0),
    ]

    monkeypatch.setattr(np, "get_news_by_urls", lambda db_path, urls: rows)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))
    items = prof.build_tools_digest_items([r[0] for r in rows], max_tools=3)

    tags = {it["url"]: it["source_tag"] for it in items}
    assert tags["https://tool1"] == "#DevTools"
    assert tags["https://tool2"] == "#Python"
    assert tags["https://tool3"] == "#Tools"


def test_build_weekly_digest_items_empty_rows(monkeypatch, tmp_path):
    import app.news_professor as np
    from app import db as db_module

    monkeypatch.setattr(np, "init_db", lambda db_path: None)
    monkeypatch.setattr(db_module, "get_top_news_for_period",
                        lambda *a, **k: [])

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))
    assert prof.build_weekly_digest_items(days_back=7, limit=5) == []


def test_build_weekly_digest_items_all_source_tags(monkeypatch, tmp_path):
    import app.news_professor as np
    from app import db as db_module

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    rows = [
        ("https://ai", "AI", "S1", "C1", "openai", 3.0, "2025-01-01T00:00:00"),
        ("https://py", "Py", "S2", "C2", "python_org", 2.0, "2025-01-01T00:00:00"),
        ("https://de", "DE", "S3", "C3", "databricks", 1.5, "2025-01-01T00:00:00"),
        ("https://sec", "Sec", "S4", "C4", "the_hacker_news", 1.0, "2025-01-01T00:00:00"),
        ("https://dev", "Dev", "S5", "C5", "github_blog", 0.5, "2025-01-01T00:00:00"),
    ]

    monkeypatch.setattr(db_module, "get_top_news_for_period",
                        lambda *a, **k: rows)

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))
    items = prof.build_weekly_digest_items(days_back=7, limit=10)

    tags = {it["url"]: it["source_tag"] for it in items}
    assert tags["https://ai"] == "#AI"
    assert tags["https://py"] == "#Python"
    assert tags["https://de"] == "#DataEngineering"
    assert tags["https://sec"] == "#Security"
    assert tags["https://dev"] == "#DevTools"


# -------- run_for_today --------


def _dummy_datetime_with_weekday(value: int):
    class DummyDateTime:
        @classmethod
        def now(cls):
            class D:
                def weekday(self_nonlocal):
                    return value
            return D()
    return DummyDateTime


def test_run_for_today_no_plan(monkeypatch):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)
    monkeypatch.setattr(np, "datetime", _dummy_datetime_with_weekday(99))

    warns = []
    monkeypatch.setattr(np, "log_warning", lambda msg: warns.append(msg))

    monkeypatch.setattr(
        np.NewsProfessor,
        "collect_links",
        lambda self, sites: (_ for _ in ()).throw(
            AssertionError("collect_links should not be called")
        ),
    )

    prof = NewsProfessor(db_path=":memory:")
    prof.run_for_today()

    assert any("нет конфига контент-плана" in m for m in warns)


def test_run_for_today_weekday_news_flow(monkeypatch):
    import app.news_professor as np

    monkeypatch.setattr(np, "init_db", lambda db_path: None)
    monkeypatch.setattr(np, "datetime", _dummy_datetime_with_weekday(1))  # Вторник

    collected = []
    fetched = []
    published = []

    def fake_collect(self, sites):
        collected.append(tuple(sites))
        return ["u1", "u2"]

    def fake_fetch_batch(self, links, substring, max_to_fetch):
        fetched.append((tuple(links), substring, max_to_fetch))
        return ["u1"]

    def fake_publish(self, urls, max_to_publish=5):
        published.append((tuple(urls), max_to_publish))

    monkeypatch.setattr(np.NewsProfessor, "collect_links", fake_collect)
    monkeypatch.setattr(np.NewsProfessor, "fetch_and_store_new_articles_batch", fake_fetch_batch)
    monkeypatch.setattr(np.NewsProfessor, "publish_top_news", fake_publish)
    monkeypatch.setattr(np, "log_info", lambda msg: None)

    prof = NewsProfessor(db_path=":memory:")
    prof.run_for_today()

    assert collected
    assert fetched
    assert published


def test_run_for_today_saturday_tools(monkeypatch):
    import app.news_professor as np
    from app import telegram_bot as tb

    monkeypatch.setattr(np, "init_db", lambda db_path: None)
    monkeypatch.setattr(np, "datetime", _dummy_datetime_with_weekday(5))  # Суббота

    monkeypatch.setattr(np.NewsProfessor, "collect_links", lambda self, sites: ["u1"])
    monkeypatch.setattr(np.NewsProfessor, "fetch_and_store_new_articles_batch",
                        lambda self, links, substring, max_to_fetch: ["u1"])

    infos = []
    monkeypatch.setattr(np, "log_info", lambda msg: infos.append(msg))

    monkeypatch.setattr(np.NewsProfessor, "build_tools_digest_items",
                        lambda self, new_urls, max_tools: [])

    prof = NewsProfessor(db_path=":memory:")
    prof.run_for_today()
    assert any("Нет новых тулзов" in m for m in infos)

    def build_tools(self, new_urls, max_tools):
        return [{
            "url": "https://tool",
            "title": "Tool",
            "summary": "",
            "use_case": "",
            "source_tag": "#DevTools",
        }]

    monkeypatch.setattr(np.NewsProfessor, "build_tools_digest_items", build_tools)

    sent = []
    monkeypatch.setattr(tb, "format_tools_digest_message", lambda tools: "TOOLS_MSG")
    monkeypatch.setattr(np, "send_message", lambda bot_token, chat_id, text: sent.append(text))

    infos.clear()
    prof.run_for_today()
    assert "TOOLS_MSG" in sent
    assert any("подборка тулзов опубликована" in m for m in infos)


def test_run_for_today_sunday_digest(monkeypatch, tmp_path):
    import app.news_professor as np
    from app import telegram_bot as tb

    # Делаем "сегодня" воскресеньем (weekday == 6)
    class DummyDateTime:
        @classmethod
        def now(cls):
            class D:
                def weekday(self_nonlocal):
                    return 6
            return D()

    monkeypatch.setattr(np, "datetime", DummyDateTime)
    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    # --- глушим сбор ссылок и парсинг, чтобы не ходить в сеть и БД ---
    monkeypatch.setattr(
        np.NewsProfessor,
        "collect_links",
        lambda self, sites: ["https://example.com/news1", "https://example.com/news2"],
    )
    monkeypatch.setattr(
        np.NewsProfessor,
        "fetch_and_store_new_articles_batch",
        lambda self, links, substring, max_to_fetch: links,
    )

    # --- мок для сборки недельного дайджеста ---
    built_items_calls = []

    def fake_build_weekly_digest_items(self, days_back: int = 7, limit: int = 8):
        built_items_calls.append({"days_back": days_back, "limit": limit})
        return [
            {"title": "Ev1", "summary": "S1", "url": "https://e1", "source_tag": "#AI"},
            {"title": "Ev2", "summary": "S2", "url": "https://e2", "source_tag": "#Python"},
        ]

    monkeypatch.setattr(
        np.NewsProfessor,
        "build_weekly_digest_items",
        fake_build_weekly_digest_items,
    )

    # --- мок форматтера и отправки сообщения ---
    formatted_events = []

    def fake_format_weekly_digest_message(events):
        # убеждаемся, что в форматтер прилетают именно наши события
        assert len(events) == 2
        formatted_events.append(events)
        return "DIGEST_MSG"

    monkeypatch.setattr(
        tb,
        "format_weekly_digest_message",
        fake_format_weekly_digest_message,
    )

    class DummySettings:
        telegram_bot_token = "TOKEN"
        telegram_chat_id = "CHAT"

    sent = []

    def fake_send_message(bot_token: str, chat_id: str, text: str):
        sent.append({"token": bot_token, "chat_id": chat_id, "text": text})

    infos = []

    monkeypatch.setattr(np, "settings", DummySettings)
    monkeypatch.setattr(np, "send_message", fake_send_message)
    monkeypatch.setattr(np, "log_info", lambda msg: infos.append(msg))
    monkeypatch.setattr(np, "log_warning", lambda msg: infos.append(msg))

    # --- запуск ---
    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))
    prof.run_for_today()

    # --- проверки ---
    # 1) build_weekly_digest_items вызвался с правильными параметрами
    assert built_items_calls
    assert built_items_calls[0]["days_back"] == 7
    assert built_items_calls[0]["limit"] == 8

    # 2) форматтер получил наши события
    assert formatted_events
    assert formatted_events[0][0]["url"] == "https://e1"

    # 3) в Telegram ушло одно сообщение с дайджестом
    assert sent == [
        {"token": "TOKEN", "chat_id": "CHAT", "text": "DIGEST_MSG"}
    ]


def test_build_weekly_digest_items_default_source_tag(monkeypatch, tmp_path):
    import app.news_professor as np
    from app import db as db_module

    monkeypatch.setattr(np, "init_db", lambda db_path: None)

    # источник не входит ни в один из известных наборов → должен быть #НовостиIT
    rows = [
        (
            "https://other",
            "Other title",
            "Other summary",
            "Other content",
            "weird_source",  # неизвестный source
            0.7,
            "2025-01-01T00:00:00",
        )
    ]

    monkeypatch.setattr(
        db_module,
        "get_top_news_for_period",
        lambda *a, **k: rows,
    )

    prof = NewsProfessor(db_path=str(tmp_path / "news.db"))
    items = prof.build_weekly_digest_items(days_back=7, limit=5)

    assert len(items) == 1
    assert items[0]["url"] == "https://other"
    assert items[0]["source_tag"] == "#НовостиIT"
