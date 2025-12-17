# tests/test_news_professor_monitoring.py
from datetime import datetime, timedelta, timezone


def test_run_monitoring_no_news_sends_alert(tmp_path, monkeypatch):
    """
    Если в базе нет ни одной новости, мониторинг должен отправить алерт.
    """
    from app import news_professor as np

    db_path = tmp_path / "news.db"
    professor = np.NewsProfessor(db_path=str(db_path))

    captured = {}

    def fake_log_error(msg: str, alert: bool = False) -> None:
        captured["msg"] = msg
        captured["alert"] = alert

    monkeypatch.setattr(np, "log_error", fake_log_error)

    professor.run_monitoring(max_days_without_news=3)

    assert captured.get("alert") is True
    assert "нет ни одной записи" in captured.get("msg", "")


def test_run_monitoring_stale_news_triggers_alert(tmp_path, monkeypatch):
    """
    Если последняя новость старше порога max_days_without_news, должен быть алерт.
    """
    from app import news_professor as np
    from app.db import get_connection

    db_path = tmp_path / "news.db"
    professor = np.NewsProfessor(db_path=str(db_path))

    old_dt = datetime.now(timezone.utc) - timedelta(days=10)
    fetched_at = old_dt.isoformat()

    # Вставляем старую новость с корректной датой
    with get_connection(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO news (url, title, summary, content, source, score, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "https://example.com/old",
                "Old news",
                "summary",
                "content",
                "source",
                1.0,
                fetched_at,
            ),
        )
        conn.commit()

    captured = {}

    def fake_log_error(msg: str, alert: bool = False) -> None:
        captured["msg"] = msg
        captured["alert"] = alert

    monkeypatch.setattr(np, "log_error", fake_log_error)

    professor.run_monitoring(max_days_without_news=3)

    assert captured.get("alert") is True
    assert "не было новых новостей уже" in captured.get("msg", "")


def test_run_monitoring_fresh_news_no_alert(tmp_path, monkeypatch):
    """
    Если последняя новость свежая, алерта быть не должно.
    """
    from app import news_professor as np
    from app.db import get_connection

    db_path = tmp_path / "news.db"
    professor = np.NewsProfessor(db_path=str(db_path))

    fresh_dt = datetime.now() - timedelta(days=1)  # naive datetime
    fetched_at = fresh_dt.isoformat()  # без "+00:00"

    with get_connection(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO news (url, title, summary, content, source, score, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "https://example.com/fresh",
                "Fresh news",
                "summary",
                "content",
                "source",
                1.0,
                fetched_at,
            ),
        )
        conn.commit()

    calls = []

    def fake_log_error(msg: str, alert: bool = False) -> None:
        calls.append((msg, alert))

    monkeypatch.setattr(np, "log_error", fake_log_error)

    professor.run_monitoring(max_days_without_news=3)

    # Не должно быть ни одного вызова с alert=True
    assert all(not alert for _, alert in calls)


def test_run_monitoring_missing_fetched_at(tmp_path, monkeypatch):
    """
    Если fetched_at отсутствует (NULL), должен быть warning и без падения.
    """
    from app import news_professor as np
    from app.db import get_connection

    db_path = tmp_path / "news.db"
    professor = np.NewsProfessor(db_path=str(db_path))

    with get_connection(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO news (url, title, summary, content, source, score, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "https://example.com/no-date",
                "No date",
                "summary",
                "content",
                "source",
                1.0,
                None,  # ← это будет NULL
            ),
        )
        conn.commit()

    captured = {}

    def fake_log_warning(msg: str) -> None:
        captured["msg"] = msg

    monkeypatch.setattr(np, "log_warning", fake_log_warning)

    professor.run_monitoring()

    assert "отсутствует fetched_at" in captured.get("msg", "")


def test_run_monitoring_invalid_fetched_at(tmp_path, monkeypatch):
    """
    Если fetched_at есть, но в неверном формате, должен быть warning про разбор даты.
    """
    from app import news_professor as np
    from app.db import get_connection

    db_path = tmp_path / "news.db"
    professor = np.NewsProfessor(db_path=str(db_path))

    with get_connection(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO news (url, title, summary, content, source, score, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "https://example.com/bad-date",
                "Bad date",
                "summary",
                "content",
                "source",
                1.0,
                "NOT_A_DATE",  # ← строка, которая не парсится fromisoformat
            ),
        )
        conn.commit()

    captured = {}

    def fake_log_warning(msg: str) -> None:
        captured["msg"] = msg

    monkeypatch.setattr(np, "log_warning", fake_log_warning)

    professor.run_monitoring()

    assert "не удалось разобрать fetched_at" in captured.get("msg", "")
