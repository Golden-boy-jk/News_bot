import logging
from logging.handlers import RotatingFileHandler


def test_setup_logging_stdout_only(monkeypatch):
    """
    Если файловое логирование выключено, должен остаться только stdout-хендлер.
    """
    from app import logging_utils

    monkeypatch.setenv("NEWS_BOT_FILE_LOGGING", "0")

    logging_utils.setup_logging()

    handlers = logging_utils.logger.handlers
    # один хендлер, и это StreamHandler (stdout)
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)


def test_setup_logging_with_file_logging(tmp_path, monkeypatch):
    """
    При включённом файловом логировании добавляются два RotatingFileHandler:
    - app.log (INFO+)
    - error.log (WARNING+)
    """
    from app import logging_utils

    monkeypatch.setenv("NEWS_BOT_FILE_LOGGING", "1")
    monkeypatch.setenv("NEWS_BOT_LOG_DIR", str(tmp_path))

    # на всякий случай опустим лимиты, но это не критично
    monkeypatch.setenv("NEWS_BOT_APP_LOG_MAX_BYTES", "1024")
    monkeypatch.setenv("NEWS_BOT_ERROR_LOG_MAX_BYTES", "1024")
    monkeypatch.setenv("NEWS_BOT_APP_LOG_BACKUP_COUNT", "1")
    monkeypatch.setenv("NEWS_BOT_ERROR_LOG_BACKUP_COUNT", "1")

    logging_utils.setup_logging()

    handlers = logging_utils.logger.handlers
    # stdout + 2 файловых хендлера как минимум
    assert len(handlers) >= 3

    file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 2

    # Логируем, чтобы файлы физически создались
    logging_utils.log_info("test info")
    logging_utils.log_warning("test warning")

    # Проверяем, что нужные файлы появились
    app_log = tmp_path / "app.log"
    error_log = tmp_path / "error.log"

    assert app_log.exists()
    assert error_log.exists()


def test_log_error_sends_alert(monkeypatch):
    """
    При alert=True должен вызываться send_error_alert с переданным текстом.
    """
    from app import logging_utils

    captured = {}

    def fake_send_alert(msg: str) -> None:
        captured["msg"] = msg

    # В модуле logging_utils send_error_alert уже импортирован,
    # поэтому патчим именно его.
    monkeypatch.setattr(logging_utils, "send_error_alert", fake_send_alert)

    logging_utils.setup_logging()
    logging_utils.log_error("boom", alert=True)

    assert captured["msg"] == "boom"


def test_log_error_alert_failure_is_swallowed(monkeypatch):
    """
    Если send_error_alert падает, log_error не должен ронять приложение.
    """
    from app import logging_utils

    def failing_alert(msg: str) -> None:
        raise RuntimeError("alert failed")

    monkeypatch.setattr(logging_utils, "send_error_alert", failing_alert)

    logging_utils.setup_logging()
    # Если здесь не выброшено исключение — всё ок, защитный try/except отработал.
    logging_utils.log_error("oops", alert=True)


def test_setup_logging_handles_log_dir_error(monkeypatch, capsys):
    """
    Если не удалось создать директорию логов (например, нет прав),
    setup_logging не должен падать и должен написать сообщение в stderr.
    """
    from app import logging_utils

    monkeypatch.setenv("NEWS_BOT_FILE_LOGGING", "1")

    def raise_makedirs(path, exist_ok=False):
        raise OSError("no permission")

    monkeypatch.setattr(logging_utils.os, "makedirs", raise_makedirs)

    logging_utils.setup_logging()

    captured = capsys.readouterr()
    # Сообщение из print(...) в except-блоке
    assert "Не удалось настроить файловое логирование" in captured.err
