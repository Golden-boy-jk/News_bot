# app/scheduler_main.py
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .logging_utils import log_error, log_info, setup_logging
from .news_professor import NewsProfessor

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def job_daily_news():
    professor = NewsProfessor(db_path=settings.database_path)
    try:
        professor.run_for_today()
    except Exception as e:
        log_error(f"Критическая ошибка в job_daily_news: {e}", alert=True)


def main():
    setup_logging()
    # Явно используем pytz-таймзону, чтобы APScheduler мог вызвать .normalize()
    scheduler = BlockingScheduler(timezone=MOSCOW_TZ)

    # Каждый день в 09:00 по Москве
    trigger = CronTrigger(hour=9, minute=0, timezone=MOSCOW_TZ)
    scheduler.add_job(job_daily_news, trigger, id="daily_news_job")

    log_info("Планировщик запущен. Ожидаю ежедневный запуск в 09:00 (Europe/Moscow).")
    scheduler.start()


if __name__ == "__main__":
    main()
