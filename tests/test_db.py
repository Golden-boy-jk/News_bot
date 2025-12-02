# tests/test_db.py
from typing import List, Tuple
import sqlite3

from app.db import (
    init_db,
    link_exists,
    save_news,
    update_score,
    get_last_news,
    get_news_by_urls,
    get_top_news_for_period,
)


def test_init_db_creates_table(tmp_path):
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='news';"
        )
        assert cur.fetchone() is not None
    finally:
        conn.close()


def test_init_db_migrates_legacy_table(tmp_path):
    """
    Создаём старую версию таблицы news (только id),
    потом вызываем init_db и ожидаем, что миграция добавит недостающие колонки.
    Это покрывает ветку с ALTER TABLE в _migrate_news_table.
    """
    db_path = tmp_path / "news.db"

    # legacy-схема без нужных колонок
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE news (
                id INTEGER PRIMARY KEY AUTOINCREMENT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    # теперь запускаем наш init_db — он должен вызвать _migrate_news_table
    init_db(str(db_path))

    # проверяем, что все нужные колонки появились
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("PRAGMA table_info(news);")
        cols = {row[1] for row in cur.fetchall()}
        assert {"url", "title", "summary", "content", "source", "score", "fetched_at"} <= cols
    finally:
        conn.close()


def test_init_db_second_call_runs_migration(tmp_path):
    """
    Первый вызов init_db -> _create_news_table,
    второй вызов -> _migrate_news_table (ветка else).
    """
    db_path = tmp_path / "news.db"
    init_db(str(db_path))   # создаём таблицу
    init_db(str(db_path))   # должна пройти миграция, но без ошибок

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("PRAGMA table_info(news);")
        cols = {row[1] for row in cur.fetchall()}
        # проверяем, что все нужные колонки на месте
        assert {"url", "title", "summary", "content", "source", "score", "fetched_at"} <= cols
    finally:
        conn.close()


def _insert_sample_news(
    db_path: str,
    url: str,
    score: float = 1.0,
):
    save_news(
        db_path=db_path,
        url=url,
        title="Title " + url,
        summary="Summary " + url,
        content="Content " + url,
        source="test_source",
        score=score,
    )


def test_save_news_and_link_exists_and_get_last_news(tmp_path):
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    assert not link_exists(str(db_path), "https://example.com/1")

    _insert_sample_news(str(db_path), "https://example.com/1", score=0.5)
    _insert_sample_news(str(db_path), "https://example.com/2", score=1.5)

    assert link_exists(str(db_path), "https://example.com/1")
    assert link_exists(str(db_path), "https://example.com/2")

    last_news = get_last_news(str(db_path), limit=1)
    assert len(last_news) == 1

    (url, title, summary, content, source, score, fetched_at) = last_news[0]
    assert url == "https://example.com/2"
    assert "Title" in title
    assert "Summary" in summary
    assert "Content" in content
    assert source == "test_source"
    assert isinstance(score, float)
    # fetched_at хранится как текст (ISO-строка)
    assert isinstance(fetched_at, str)


def test_manual_update_of_fetched_at(tmp_path):
    """
    Косвенно покрываем работу с колонкой fetched_at:
    сохраняем новость, затем руками обновляем timestamp
    и убеждаемся, что get_last_news читает его корректно.
    """
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    url = "https://example.com/custom"
    _insert_sample_news(str(db_path), url, score=2.0)

    custom_ts = "2000-01-01T00:00:00"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE news SET fetched_at = ? WHERE url = ?;",
            (custom_ts, url),
        )
        conn.commit()
    finally:
        conn.close()

    rows = get_last_news(str(db_path), limit=1)
    assert len(rows) == 1
    (r_url, _, _, _, _, _, fetched_at) = rows[0]
    assert r_url == url
    assert fetched_at.startswith("2000-01-01")


def test_get_news_by_urls_and_update_score(tmp_path):
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    _insert_sample_news(str(db_path), "https://example.com/a", score=0.1)
    _insert_sample_news(str(db_path), "https://example.com/b", score=0.2)

    rows = get_news_by_urls(
        str(db_path),
        ["https://example.com/a", "https://example.com/b"],
    )
    assert len(rows) == 2

    update_score(str(db_path), "https://example.com/a", score=5.0)
    rows2 = get_news_by_urls(str(db_path), ["https://example.com/a"])
    assert len(rows2) == 1
    (url, title, summary, content, source, score) = rows2[0]
    assert url == "https://example.com/a"
    assert score == 5.0


def test_update_score_for_nonexistent_url_does_not_crash(tmp_path):
    """
    Ветка: UPDATE по URL, которого нет.
    Запрос ничего не обновит, но и не должен упасть.
    """
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    update_score(str(db_path), "https://example.com/missing", score=10.0)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM news;")
        assert cur.fetchone()[0] == 0
    finally:
        conn.close()


def test_get_news_by_urls_with_empty_list_returns_empty(tmp_path):
    """
    Пустой список URL → ранний return [] (ветка if not urls).
    """
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    _insert_sample_news(str(db_path), "https://example.com/a", score=1.0)

    rows = get_news_by_urls(str(db_path), [])
    assert rows == []


def test_get_top_news_for_period_ordering(tmp_path):
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    _insert_sample_news(str(db_path), "https://example.com/low", score=0.1)
    _insert_sample_news(str(db_path), "https://example.com/mid", score=1.0)
    _insert_sample_news(str(db_path), "https://example.com/high", score=5.0)

    rows = get_top_news_for_period(str(db_path), days_back=365, limit=3)
    urls_in_order = [r[0] for r in rows]

    assert urls_in_order[0] == "https://example.com/high"
    assert set(urls_in_order) == {
        "https://example.com/low",
        "https://example.com/mid",
        "https://example.com/high",
    }


def test_get_top_news_for_period_zero_limit_returns_empty(tmp_path):
    """
    LIMIT 0 → SQLite вернёт 0 строк, мы должны получить [].
    """
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    _insert_sample_news(str(db_path), "https://example.com/x", score=10.0)

    rows = get_top_news_for_period(str(db_path), days_back=365, limit=0)
    assert rows == []


def test_get_top_news_for_period_no_news_in_period(tmp_path):
    """
    Ветка, когда по дате ничего не попадает в диапазон:
    делаем fetched_at очень старым и берём маленький days_back.
    """
    db_path = tmp_path / "news.db"
    init_db(str(db_path))

    url = "https://example.com/old"
    _insert_sample_news(str(db_path), url, score=100.0)

    # Сдвигаем fetched_at далеко в прошлое
    old_ts = "2000-01-01T00:00:00"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE news SET fetched_at = ? WHERE url = ?;",
            (old_ts, url),
        )
        conn.commit()
    finally:
        conn.close()

    rows = get_top_news_for_period(str(db_path), days_back=1, limit=10)
    assert rows == []
