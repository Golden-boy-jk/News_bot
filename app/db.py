# app/db.py
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Tuple


@contextmanager
def get_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def _create_news_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            title TEXT,
            summary TEXT,
            content TEXT,
            source TEXT,
            score REAL,
            fetched_at TEXT
        );
        """
    )


def _migrate_news_table(conn):
    cur = conn.execute("PRAGMA table_info(news);")
    existing_columns = {row[1] for row in cur.fetchall()}

    needed_columns = {
        "url": "TEXT",
        "title": "TEXT",
        "summary": "TEXT",
        "content": "TEXT",
        "source": "TEXT",
        "score": "REAL",
        "fetched_at": "TEXT",
    }

    for col_name, col_def in needed_columns.items():
        if col_name not in existing_columns:
            conn.execute(f"ALTER TABLE news ADD COLUMN {col_name} {col_def};")


def init_db(db_path: str) -> None:
    with get_connection(db_path) as conn:
        if not _table_exists(conn, "news"):
            _create_news_table(conn)
        else:
            _migrate_news_table(conn)
        conn.commit()


def link_exists(db_path: str, url: str) -> bool:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT 1 FROM news WHERE url = ? LIMIT 1", (url,))
        return cur.fetchone() is not None


def save_news(
    db_path: str,
    url: str,
    title: Optional[str],
    summary: Optional[str],
    content: str,
    source: Optional[str],
    score: Optional[float],
) -> None:
    fetched_at = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO news (url, title, summary, content, source, score, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (url, title, summary, content, source, score, fetched_at),
        )
        conn.commit()


def update_score(db_path: str, url: str, score: float) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE news SET score = ? WHERE url = ?;",
            (score, url),
        )
        conn.commit()


def get_last_news(db_path: str, limit: int = 5):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT url, title, summary, content, source, score, fetched_at
            FROM news
            ORDER BY id DESC
            LIMIT ?;
            """,
            (limit,),
        )
        return cur.fetchall()


def get_news_by_urls(
    db_path: str, urls: Iterable[str]
) -> List[Tuple[str, str, str, str, Optional[str], Optional[float]]]:
    urls = list(urls)
    if not urls:
        return []

    placeholders = ",".join("?" for _ in urls)
    query = f"""
        SELECT url, title, summary, content, source, score
        FROM news
        WHERE url IN ({placeholders});
    """

    with get_connection(db_path) as conn:
        cur = conn.execute(query, urls)
        return [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in cur.fetchall()]


def get_top_news_for_period(
    db_path: str,
    days_back: int = 7,
    limit: int = 8,
):
    """
    Возвращает топ-новости за последние days_back дней по score.
    Используется для воскресного дайджеста.
    """
    since = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT url, title, summary, content, source, score, fetched_at
            FROM news
            WHERE fetched_at >= ?
            ORDER BY score DESC, fetched_at DESC
            LIMIT ?;
            """,
            (since, limit),
        )
        return cur.fetchall()
