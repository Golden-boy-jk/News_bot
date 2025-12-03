# tests/test_logging_utils.py
import logging


def test_setup_logging_adds_handler(monkeypatch):
    import app.logging_utils as lu

    # Сбрасываем handlers, чтобы тест был детерминированным
    lu.logger.handlers.clear()

    lu.setup_logging(level=logging.DEBUG)

    # После setup_logging должен появиться хотя бы один handler
    assert lu.logger.level == logging.DEBUG
    assert len(lu.logger.handlers) == 1
    handler = lu.logger.handlers[0]
    # handler пишет в stdout (StreamHandler)
    assert isinstance(handler, logging.StreamHandler)


def test_log_info_uses_logger_info(monkeypatch):
    import app.logging_utils as lu

    calls = []

    def fake_info(msg):
        calls.append(msg)

    monkeypatch.setattr(lu.logger, "info", fake_info)

    lu.log_info("hello info")

    assert calls == ["hello info"]


def test_log_warning_uses_logger_warning(monkeypatch):
    import app.logging_utils as lu

    calls = []

    def fake_warning(msg):
        calls.append(msg)

    monkeypatch.setattr(lu.logger, "warning", fake_warning)

    lu.log_warning("something happened")

    assert calls == ["something happened"]


def test_log_error_without_alert(monkeypatch):
    import app.logging_utils as lu

    logged = []

    def fake_error(msg):
        logged.append(msg)

    # Подменяем только logger.error, send_error_alert не должен вызываться
    monkeypatch.setattr(lu.logger, "error", fake_error)

    lu.log_error("simple error", alert=False)

    assert logged == ["simple error"]


def test_log_error_with_alert_success(monkeypatch):
    import app.logging_utils as lu

    logged = []
    alerts = []

    def fake_error(msg):
        logged.append(msg)

    def fake_send_error_alert(msg):
        alerts.append(msg)

    monkeypatch.setattr(lu.logger, "error", fake_error)
    monkeypatch.setattr(lu, "send_error_alert", fake_send_error_alert)

    lu.log_error("fatal error", alert=True)

    # Сначала логируем основное сообщение
    assert "fatal error" in logged[0]
    # Затем вызывается send_error_alert
    assert alerts == ["fatal error"]
    # Дополнительных ошибок не должно быть
    assert len(logged) == 1


def test_log_error_with_alert_failure(monkeypatch):
    import app.logging_utils as lu

    logged = []

    def fake_error(msg):
        logged.append(msg)

    def fake_send_error_alert(msg):
        raise RuntimeError("boom")

    monkeypatch.setattr(lu.logger, "error", fake_error)
    monkeypatch.setattr(lu, "send_error_alert", fake_send_error_alert)

    lu.log_error("critical error", alert=True)

    # Первое сообщение — оригинальная ошибка
    assert "critical error" in logged[0]
    # Второе сообщение — текст из except
    assert any("Не удалось отправить алерт в Telegram" in m for m in logged[1:])
