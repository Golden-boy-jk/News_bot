# app/scheduler_main.py
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .news_professor import NewsProfessor
from .logging_utils import setup_logging, log_info, log_error


def job_daily_news():
    professor = NewsProfessor(db_path=settings.database_path)
    try:
        professor.run_for_today()
    except Exception as e:
        log_error(f"Критическая ошибка в job_daily_news: {e}", alert=True)


def main():
    setup_logging()
    scheduler = BlockingScheduler(timezone="Europe/Moscow")

    # Каждый день в 09:00 по Москве
    trigger = CronTrigger(hour=9, minute=0)
    scheduler.add_job(job_daily_news, trigger, id="daily_news_job")

    log_info("Планировщик запущен. Ожидаю ежедневный запуск в 09:00 (Europe/Moscow).")
    scheduler.start()


if __name__ == "__main__":
    main()
