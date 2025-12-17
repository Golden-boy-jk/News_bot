# app/main.py
from .config import get_settings
from .logging_utils import setup_logging
from .news_professor import NewsProfessor


def main():
    setup_logging()

    settings = get_settings()

    professor = NewsProfessor(db_path=settings.database_path)
    professor.run_for_today()


if __name__ == "__main__":
    main()
