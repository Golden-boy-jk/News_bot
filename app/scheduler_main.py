from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from .config import get_settings
from .news_professor import NewsProfessor
from .logging_utils import setup_logging, log_info, log_error


def job_daily_news() -> None:
    try:
        settings = get_settings()
        professor = NewsProfessor(db_path=settings.database_path)
        professor.run_for_today()
    except Exception as e:
        log_error(f"Критическая ошибка в job_daily_news: {e}", alert=True)


def job_monitoring() -> None:
    """
    Ежедневная задача мониторинга:
    - проверяет свежесть новостей;
    - при необходимости отправляет алерты.
    """
    try:
        settings = get_settings()
        professor = NewsProfessor(db_path=settings.database_path)
        professor.run_monitoring()
    except Exception as e:
        log_error(f"Критическая ошибка в job_monitoring: {e}", alert=True)


def main() -> None:
    setup_logging()

    # Явно используем pytz.timezone, чтобы APScheduler получил tz с методом .localize
    moscow_tz = pytz.timezone("Europe/Moscow")
    scheduler = BlockingScheduler(timezone=moscow_tz)

    # Каждый день в 09:00 по Москве — основной запуск новостей
    trigger_news = CronTrigger(hour=9, minute=0, timezone=moscow_tz)
    scheduler.add_job(job_daily_news, trigger_news, id="daily_news_job")

    # Каждый день в 10:00 по Москве — мониторинг
    trigger_monitor = CronTrigger(hour=10, minute=0, timezone=moscow_tz)
    scheduler.add_job(job_monitoring, trigger_monitor, id="monitoring_job")

    log_info(
        "Планировщик запущен. "
        "Ежедневный запуск новостей в 09:00 и мониторинга в 10:00 (Europe/Moscow)."
    )
    scheduler.start()


if __name__ == "__main__":
    main()
