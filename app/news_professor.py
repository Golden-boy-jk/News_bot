# app/news_professor.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Dict, Tuple, Optional

from .config import settings
from .db import (
    init_db,
    link_exists,
    save_news,
    get_news_by_urls,
)
from .filters import filter_link_by_substring
from .link_extractor import extract_links_from_url
from .text_parser import fetch_text_content
from .telegram_bot import format_news_message, send_message
from .scoring import compute_tfidf_scores
from .logging_utils import log_info, log_warning, log_error


# ---------- Наборы сайтов под тематику ----------

# Понедельник — AI / нейросети
SITES_AI: List[str] = [
    "https://openai.com",
    "https://blog.google/technology/ai/",
    "https://www.anthropic.com/news",
    "https://huggingface.co/blog",
    "https://stability.ai/news",
]

# Вторник — Python
SITES_PYTHON: List[str] = [
    "https://www.python.org/blogs/",
    "https://realpython.com/tutorials/news/",
    "https://blog.jetbrains.com/pycharm/",
    "https://www.pythonweekly.com/",
]

# Среда — Data Engineering / Big Data
SITES_DATA_ENG: List[str] = [
    "https://www.databricks.com/blog",
    "https://www.confluent.io/blog/",
    "https://aws.amazon.com/blogs/big-data/",
]

# Четверг — Security
SITES_SECURITY: List[str] = [
    "https://thehackernews.com/",
    "https://gbhackers.com/",
    "https://cybersecuritynews.com/",
]

# Пятница — DevTools / сервисы
SITES_DEVTOOLS: List[str] = [
    "https://github.blog/news-insights/",
    "https://code.visualstudio.com/updates",
    "https://www.docker.com/blog/",
]

# Суббота — подборка тулзов (DevTools + Python)
SITES_TOOLS_DAY: List[str] = SITES_DEVTOOLS + SITES_PYTHON

# Воскресенье — дайджест (всё подряд)
ALL_SITES: List[str] = (
    SITES_AI
    + SITES_PYTHON
    + SITES_DATA_ENG
    + SITES_SECURITY
    + SITES_DEVTOOLS
)


@dataclass
class ContentPlanConfig:
    """
    Конфиг на день недели:
    - sites: откуда тянем новости
    - substring: фильтр по URL (обычно /2025/)
    - max_fetch: сколько максимум новых статей за раз сохраняем
    """
    sites: List[str]
    substring: str
    max_fetch: int


# 0 = Пн, 6 = Вс
CONTENT_PLAN: Dict[int, ContentPlanConfig] = {
    0: ContentPlanConfig(  # Понедельник — AI/нейросети
        sites=SITES_AI,
        substring="/2025/",
        max_fetch=40,
    ),
    1: ContentPlanConfig(  # Вторник — Python
        sites=SITES_PYTHON,
        substring="/2025/",
        max_fetch=40,
    ),
    2: ContentPlanConfig(  # Среда — Data Engineering
        sites=SITES_DATA_ENG,
        substring="/2025/",
        max_fetch=40,
    ),
    3: ContentPlanConfig(  # Четверг — Security
        sites=SITES_SECURITY,
        substring="/2025/",
        max_fetch=40,
    ),
    4: ContentPlanConfig(  # Пятница — DevTools / сервисы
        sites=SITES_DEVTOOLS,
        substring="/2025/",
        max_fetch=40,
    ),
    5: ContentPlanConfig(  # Суббота — подборка тулзов
        sites=SITES_TOOLS_DAY,
        substring="/2025/",
        max_fetch=60,
    ),
    6: ContentPlanConfig(  # Воскресенье — дайджест недели
        sites=ALL_SITES,
        substring="/2025/",
        max_fetch=80,
    ),
}


DAY_TOPIC_TAGS: Dict[int, Dict[str, str]] = {
    0: {"topic_tag": "#AI", "source_tag": "#Нейросети"},        # Пн
    1: {"topic_tag": "#Python", "source_tag": "#Разработка"},   # Вт
    2: {"topic_tag": "#DataEngineering", "source_tag": "#BigData"},  # Ср
    3: {"topic_tag": "#Security", "source_tag": "#DevSecOps"},  # Чт
    4: {"topic_tag": "#Tools", "source_tag": "#DevTools"},      # Пт
    5: {"topic_tag": "#Tools", "source_tag": "#Подборка"},      # Сб
    6: {"topic_tag": "#Digest", "source_tag": "#Дайджест"},     # Вс
}


def get_today_tags() -> Dict[str, str]:
    weekday = datetime.now().weekday()
    return DAY_TOPIC_TAGS.get(weekday, {"topic_tag": "#НовостиIT", "source_tag": "#IT"})


def guess_source_from_url(url: str) -> str:
    url = url.lower()

    # AI
    if "openai.com" in url:
        return "openai"
    if "blog.google/technology/ai" in url:
        return "google_ai_blog"
    if "anthropic.com" in url:
        return "anthropic"
    if "huggingface.co" in url:
        return "huggingface"
    if "stability.ai" in url:
        return "stability_ai"

    # Python
    if "python.org" in url:
        return "python_org"
    if "realpython.com" in url:
        return "realpython"
    if "blog.jetbrains.com/pycharm" in url:
        return "pycharm_blog"
    if "pythonweekly.com" in url:
        return "python_weekly"

    # Data Engineering
    if "databricks.com" in url:
        return "databricks"
    if "confluent.io" in url:
        return "confluent"
    if "aws.amazon.com/blogs/big-data" in url:
        return "aws_bigdata"

    # Security
    if "thehackernews.com" in url:
        return "the_hacker_news"
    if "gbhackers.com" in url:
        return "gbhackers"
    if "cybersecuritynews.com" in url:
        return "cybersecuritynews"

    # DevTools
    if "github.blog" in url:
        return "github_blog"
    if "code.visualstudio.com/updates" in url:
        return "vscode_updates"
    if "docker.com/blog" in url:
        return "docker_blog"

    return "other"


def split_title_and_summary(content: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Берём первую строку как title, следующие 2–3 строки склеиваем в summary.
    """
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        return None, None

    title = lines[0][:200]
    body_lines = lines[1:4]  # 2–3 строки
    summary = " ".join(body_lines)[:600] if body_lines else None
    return title, summary


def build_tool_use_case(source: str) -> str:
    """
    Простейшая эвристика по источнику для юзкейса.
    Можно потом усложнить по ключевым словам.
    """
    src = (source or "other").lower()

    if src in {"github_blog"}:
        return "Следить за новыми возможностями GitHub и улучшать свой workflow с репозиториями и CI/CD."
    if src in {"vscode_updates"}:
        return "Получать новые фичи в VS Code и прокачивать удобство ежедневного кодинга."
    if src in {"docker_blog"}:
        return "Упростить контейнеризацию приложений и работу с окружениями через Docker."
    if src in {"python_org", "realpython", "pycharm_blog", "python_weekly"}:
        return "Прокачать разработку на Python и отслеживать новые фичи экосистемы."
    if src in {"databricks", "confluent", "aws_bigdata"}:
        return "Упростить работу с data-пайплайнами, стримингом и аналитикой больших данных."
    return "Поможет упростить повседневную работу разработчика и сэкономить время."


class NewsProfessor:
    """
    Оркестратор:
    - собирает ссылки по контент-плану
    - парсит текст
    - ранжирует статьи (TF-IDF + ключевые слова)
    - пишет в БД
    - публикует топ в Telegram
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        init_db(self.db_path)

    def collect_links(self, sites: Iterable[str]) -> List[str]:
        all_links: List[str] = []
        for site in sites:
            try:
                log_info(f"Загружаю ссылки с {site}")
                links = extract_links_from_url(site)
                log_info(f"{site}: найдено {len(links)} ссылок")
                all_links.extend(links)
            except Exception as e:
                log_error(f"Ошибка при обработке {site}: {e}", alert=True)
        return all_links

    def fetch_and_store_new_articles_batch(
        self,
        links: Iterable[str],
        substring: str,
        max_to_fetch: int,
    ) -> List[str]:
        """
        - фильтруем ссылки по подстроке (например, /2025/)
        - пропускаем те, что уже есть в БД
        - парсим контент, считаем TF-IDF score, сохраняем в БД
        Возвращает список URL-ов новых статей.
        """
        filtered_links = filter_link_by_substring(links, substring)
        log_info(f"После фильтра по '{substring}' осталось {len(filtered_links)} ссылок")

        new_articles: List[Tuple[str, str, Optional[str], str, str]] = []
        # (url, title, summary, content, source)

        for url in filtered_links:
            if len(new_articles) >= max_to_fetch:
                break

            if link_exists(self.db_path, url):
                continue

            try:
                content = fetch_text_content(url)
            except Exception as e:
                log_error(f"Ошибка парсинга {url}: {e}", alert=False)
                continue

            if not content:
                continue

            title, summary = split_title_and_summary(content)
            source = guess_source_from_url(url)
            new_articles.append((url, title or "", summary or "", content, source))

        if not new_articles:
            log_info("Новых статей для сохранения нет.")
            return []

        # TF-IDF ранжирование
        texts_for_scoring = [
            f"{title}\n{summary}\n{content}" for _, title, summary, content, _ in new_articles
        ]
        scores = compute_tfidf_scores(texts_for_scoring)

        # Сохраняем в БД
        for (url, title, summary, content, source), score in zip(new_articles, scores):
            save_news(
                self.db_path,
                url=url,
                title=title,
                summary=summary,
                content=content,
                source=source,
                score=score,
            )
            log_info(f"Сохранена новость: {url} (score={score:.3f})")

        return [url for url, *_ in new_articles]

    def publish_top_news(self, new_urls: List[str], max_to_publish: int = 5) -> None:
        """
        Берём только что сохранённые новости, сортируем по score и публикуем топ-N.
        """
        if not new_urls:
            log_info("Новых новостей нет, публиковать нечего.")
            return

        rows = get_news_by_urls(self.db_path, new_urls)
        if not rows:
            log_warning("get_news_by_urls вернул пустой результат.")
            return

        # rows: (url, title, summary, content, source, score)
        scored = []
        for url, title, summary, content, source, score in rows:
            scored.append((score or 0.0, url, title, summary, content, source))

        scored.sort(reverse=True, key=lambda x: x[0])
        top = scored[:max_to_publish]

        tags = get_today_tags()
        topic_tag = tags["topic_tag"]
        default_source_tag = tags["source_tag"]

        for score, url, title, summary, content, source, in top:
            if source in {"openai", "anthropic", "huggingface", "stability_ai", "google_ai_blog"}:
                source_tag = "#AI"
            elif source in {"python_org", "realpython", "pycharm_blog", "python_weekly"}:
                source_tag = "#Python"
            elif source in {"databricks", "confluent", "aws_bigdata"}:
                source_tag = "#DataEngineering"
            elif source in {"the_hacker_news", "gbhackers", "cybersecuritynews"}:
                source_tag = "#Security"
            elif source in {"github_blog", "vscode_updates", "docker_blog"}:
                source_tag = "#DevTools"
            else:
                source_tag = default_source_tag

            msg = format_news_message(
                url=url,
                content=content,
                topic_tag=topic_tag,
                source_tag=source_tag,
            )
            send_message(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                text=msg,
            )
            log_info(f"Опубликована новость (score={score:.3f}): {url}")

    def build_tools_digest_items(self, new_urls: List[str], max_tools: int = 5) -> List[dict]:
        """
        Собирает данные для субботней подборки тулзов:
        берём новости по url, сортируем по score и возвращаем первые max_tools.
        Каждый элемент: {title, summary, url, use_case, source_tag}
        """
        if not new_urls:
            return []

        rows = get_news_by_urls(self.db_path, new_urls)
        if not rows:
            return []

        # rows: (url, title, summary, content, source, score)
        items = []
        for url, title, summary, content, source, score in rows:
            items.append({
                "url": url,
                "title": (title or "Новый инструмент")[:120],
                "summary": (summary or "").strip()[:250],
                "source": source or "other",
                "score": score or 0.0,
            })

        # сортируем по score
        items.sort(key=lambda x: x["score"], reverse=True)
        items = items[:max_tools]

        # добавляем use_case и source_tag
        for it in items:
            src = it["source"]
            it["use_case"] = build_tool_use_case(src)

            if src in {"github_blog", "vscode_updates", "docker_blog"}:
                it["source_tag"] = "#DevTools"
            elif src in {"python_org", "realpython", "pycharm_blog", "python_weekly"}:
                it["source_tag"] = "#Python"
            else:
                it["source_tag"] = "#Tools"

        return items


    def run_for_today(self) -> None:
        """
        Основной метод: дергается планировщиком раз в день в 09:00 по Москве.
        Будни: обычные новости.
        Суббота: подборка тулзов.
        Воскресенье: дайджест недели.
        """
        weekday = datetime.now().weekday()
        plan = CONTENT_PLAN.get(weekday)
        if not plan:
            log_warning(f"Для weekday={weekday} нет конфига контент-плана.")
            return

        log_info(f"Запуск Профессора новостей для weekday={weekday}")

        # 1. Собираем ссылки по списку сайтов для этого дня
        all_links = self.collect_links(plan.sites)

        # 2. Фильтруем, парсим, сохраняем новые статьи
        new_urls = self.fetch_and_store_new_articles_batch(
            links=all_links,
            substring=plan.substring,
            max_to_fetch=plan.max_fetch,
        )

        if weekday in {0, 1, 2, 3, 4}:
            # Пн–Пт — обычные новости (топ-5 по score)
            self.publish_top_news(new_urls, max_to_publish=5)
            log_info("Запуск Профессора новостей (будний день) завершён.")
        elif weekday == 5:
            # Суббота — подборка тулзов
            tools = self.build_tools_digest_items(new_urls, max_tools=5)
            from .telegram_bot import format_tools_digest_message

            if not tools:
                log_info("Нет новых тулзов для субботней подборки.")
            else:
                msg = format_tools_digest_message(tools)
                send_message(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id,
                    text=msg,
                )
                log_info("Субботняя подборка тулзов опубликована.")
        elif weekday == 6:
            # Воскресенье — дайджест недели
            events = self.build_weekly_digest_items(days_back=7, limit=8)
            from .telegram_bot import format_weekly_digest_message

            msg = format_weekly_digest_message(events)
            send_message(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                text=msg,
            )
            log_info("Воскресный дайджест недели опубликован.")

    def build_weekly_digest_items(self, days_back: int = 7, limit: int = 8) -> List[dict]:
        """
        Собирает топ событий за N дней для воскресного дайджеста.
        Возвращает список элементов {title, summary, url, source_tag}.
        """
        from .db import get_top_news_for_period  # локальный импорт, чтобы избежать циклических

        rows = get_top_news_for_period(self.db_path, days_back=days_back, limit=limit)
        if not rows:
            return []

        items = []
        for url, title, summary, content, source, score, fetched_at in rows:
            src = source or "other"

            if src in {"openai", "anthropic", "huggingface", "stability_ai", "google_ai_blog"}:
                source_tag = "#AI"
            elif src in {"python_org", "realpython", "pycharm_blog", "python_weekly"}:
                source_tag = "#Python"
            elif src in {"databricks", "confluent", "aws_bigdata"}:
                source_tag = "#DataEngineering"
            elif src in {"the_hacker_news", "gbhackers", "cybersecuritynews"}:
                source_tag = "#Security"
            elif src in {"github_blog", "vscode_updates", "docker_blog"}:
                source_tag = "#DevTools"
            else:
                source_tag = "#НовостиIT"

            items.append({
                "url": url,
                "title": (title or "Событие недели")[:140],
                "summary": (summary or "").strip()[:260],
                "source_tag": source_tag,
                "score": score or 0.0,
            })

        # уже отсортировано по score в SQL, но на всякий случай:
        items.sort(key=lambda x: x["score"], reverse=True)
        return items
