# tests/test_healthcheck.py
from contextlib import contextmanager
from types import SimpleNamespace


def test_healthcheck_ok(monkeypatch):
    import app.healthcheck as hc

    calls_info = []
    calls_error = []

    fake_settings = SimpleNamespace(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        database_path="/tmp/news.db",
    )
    monkeypatch.setattr(hc, "get_settings", lambda: fake_settings)

    monkeypatch.setattr(hc, "log_info", lambda msg: calls_info.append(msg))
    monkeypatch.setattr(
        hc,
        "log_error",
        lambda msg, alert=False: calls_error.append((msg, alert)),
    )

    class DummyConn:
        def execute(self, _sql: str) -> None:
            return None

    @contextmanager
    def good_conn(_path: str):
        yield DummyConn()

    monkeypatch.setattr(hc, "get_connection", good_conn)

    assert hc.check_settings() is True
    assert hc.check_db() is True
    assert hc.main() == 0

    assert any("Healthcheck: OK" in msg for msg in calls_info)
    assert not calls_error


def test_healthcheck_bad_settings(monkeypatch):
    import app.healthcheck as hc

    calls_error = []

    fake_settings = SimpleNamespace(
        telegram_bot_token="",
        telegram_chat_id="",
        database_path="",
    )
    monkeypatch.setattr(hc, "get_settings", lambda: fake_settings)

    monkeypatch.setattr(
        hc,
        "log_error",
        lambda msg, alert=False: calls_error.append((msg, alert)),
    )

    assert hc.check_settings() is False
    assert any("TELEGRAM_*" in msg for msg, _ in calls_error)
    assert any("DATABASE_PATH" in msg for msg, _ in calls_error)


def test_healthcheck_db_failure(monkeypatch):
    import app.healthcheck as hc

    calls_error = []

    fake_settings = SimpleNamespace(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        database_path="/tmp/news.db",
    )
    monkeypatch.setattr(hc, "get_settings", lambda: fake_settings)

    monkeypatch.setattr(
        hc,
        "log_error",
        lambda msg, alert=False: calls_error.append((msg, alert)),
    )

    @contextmanager
    def bad_conn(_path: str):
        raise RuntimeError("boom")  # noqa: TRY003
        yield  # pragma: no cover

    monkeypatch.setattr(hc, "get_connection", bad_conn)
    monkeypatch.setattr(hc, "check_settings", lambda: True)

    assert hc.check_db() is False
    assert hc.main() == 1
    assert any("ошибка доступа к БД" in msg for msg, _ in calls_error)
    assert any("Healthcheck: FAILED" in msg for msg, _ in calls_error)
