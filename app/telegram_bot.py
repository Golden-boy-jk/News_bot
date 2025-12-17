# app/telegram_bot.py
from __future__ import annotations

from html import escape
from typing import Dict, Iterable, List, Optional, Tuple

from telegram import Bot
from telegram.error import TelegramError

from .logging_utils import log_error
from .text_utils import truncate_message

TELEGRAM_MAX_LEN = 4096


def _safe(text: str) -> str:
    """Escape external/user text for Telegram HTML parse_mode."""
    return escape(text or "", quote=False)


def _safe_url(url: str) -> str:
    """Escape URL for putting into href attribute."""
    return escape(url or "", quote=True)


def _chunks(text: str, limit: int = TELEGRAM_MAX_LEN) -> Iterable[str]: # pragma: no cover
    """
    Split long text into chunks <= limit.
    Prefer splitting by newline to keep readability.
    """
    if len(text) <= limit:
        yield text
        return

    start = 0
    n = len(text)
    while start < n:
        end = min(start + limit, n)
        cut = text.rfind("\n", start, end)
        if cut == -1 or cut <= start + 200:  # avoid too tiny chunks
            cut = end
        yield text[start:cut]
        start = cut


def split_title_and_body(content: str) -> Tuple[str, str]:
    lines = [line.strip() for line in (content or "").splitlines() if line.strip()]
    if not lines:
        return "Свежая новость из мира IT", ""

    title = lines[0][:200]
    body = " ".join(lines[1:])[:800]
    return title, body


def build_post_html(*, what: str, why: str, source_url: str, humor: str, hashtags: str) -> str:
    what_e = _safe(what)
    why_e = _safe(why)
    humor_e = _safe(humor)
    hashtags_e = _safe(hashtags)
    url_e = _safe(source_url)


    return (
        f"💡 Что произошло: {what_e}\n\n"
        f"📌 Почему это важно: {why_e}\n\n"
        f"🔗 Источник: {url_e}\n\n"
        f"😅 Юмор: {humor_e}\n\n"
        f"{hashtags_e}"
    )


def send_message(bot_token: str, chat_id: str, text: str) -> Optional[str]:
    """
    Единая точка отправки:
    - truncate_message (твоя логика ограничения)
    - chunking по лимиту Telegram
    - HTML parse_mode
    """
    bot = Bot(token=bot_token)

    # Оставляем твою страховку по длине (если она есть в проекте)
    text = truncate_message(text)

    last_message_id: Optional[str] = None
    try:
        for part in _chunks(text):
            msg = bot.send_message(
                chat_id=chat_id,
                text=part,
                parse_mode="HTML",
            )
            last_message_id = str(msg.message_id)
        return last_message_id
    except TelegramError as e:
        log_error(f"Ошибка отправки сообщения в Telegram: {e}", alert=True)
        return None


def format_news_message(
    url: str,
    content: str,
    topic_tag: str = "#AI",
    source_tag: str = "#НовостиIT",
) -> str:
    title, body = split_title_and_body(content)
    what_happened = f"{title}\n\n{body}" if body else title

    why_important = "Это часть свежих изменений в мире IT и AI — полезно, чтобы не отставать от трендов."
    humor = "Похоже, новости обновляются быстрее, чем наши пет-проекты в GitHub 😅"
    hashtags = f"#НовостиIT {topic_tag} {source_tag}"

    return build_post_html(
        what=what_happened,
        why=why_important,
        source_url=url,
        humor=humor,
        hashtags=hashtags,
    )


def format_tools_digest_message(tools: List[Dict]) -> str:
    """
    Субботняя подборка тулзов.
    tools: [{title, summary, url, use_case, source_tag}]
    """
    if not tools: # pragma: no cover
        return build_post_html(
            what="На этой неделе не нашёл достойных тулзов для подборки.",
            why="Значит, можно спокойно закрыть техдолг и допилить тесты 😄",
            source_url="",
            humor="Иногда лучший инструмент — это пауза и чистый backlog 😅",
            hashtags="#НовостиIT #Tools #Подборка",
        )

    lines: List[str] = []
    lines.append("Сегодня собрал подборку свежих тулзов и сервисов для разработчиков 👇\n")

    for idx, tool in enumerate(tools, start=1):
        title = tool.get("title") or "Новый инструмент"
        summary = tool.get("summary") or ""
        url = tool.get("url") or ""
        use_case = tool.get("use_case") or "Поможет упростить жизнь разработчику."
        source_tag = tool.get("source_tag") or "#Tools"

        # Внутри 'what' держим обычный текст — build_post_html сам всё экранирует.
        block = (
            f"{idx}) {title} {source_tag}\n"
            f"   {summary}\n"
            f"   Юзкейс: {use_case}\n"
            f"   🔗 {url}\n"
        )
        lines.append(block)

    what_happened = "\n".join(lines).strip()
    why_important = "Такие инструменты экономят время, снижают рутину и помогают сосредоточиться на фичах."
    humor = "Главное — не поставить все тулзы сразу и не провести выходные в настройке окружения 😅"

    # В поле source_url оставим ссылку на первый инструмент (если есть), чтобы блок 🔗 был кликабельным.
    first_url = tools[0].get("url") or ""

    return build_post_html(
        what=what_happened,
        why=why_important,
        source_url=first_url,
        humor=humor,
        hashtags="#НовостиIT #Tools #Подборка",
    )


def format_weekly_digest_message(events: List[Dict]) -> str:
    """
    Воскресный дайджест недели.
    events: [{title, summary, url, source_tag}]
    """
    if not events: # pragma: no cover
        return build_post_html(
            what="На этой неделе громких новостей почти не было — отличный шанс догнать пет-проекты.",
            why="Даже тишина в новостях — сигнал, что можно спокойно поучиться и поэкспериментировать.",
            source_url="",
            humor="Иногда лучший релиз — это отпуск от новостной ленты 😅",
            hashtags="#НовостиIT #Digest #Дайджест",
        )

    intro = (
        "За прошедшую неделю в мире IT и AI произошло несколько важных событий. "
        "Вот краткий дайджест, чтобы не рыться в ленте весь день 👇\n"
    )

    blocks: List[str] = [intro]
    for idx, ev in enumerate(events, start=1):
        title = ev.get("title") or "Событие недели"
        summary = ev.get("summary") or ""
        url = ev.get("url") or ""
        source_tag = ev.get("source_tag") or "#НовостиIT"

        block = (
            f"{idx}) {title} {source_tag}\n"
            f"   {summary}\n"
            f"   🔗 {url}\n"
        )
        blocks.append(block)

    what_happened = "\n".join(blocks).strip()
    why_important = (
        "Такой срез по неделе помогает видеть общие тренды: куда двигаются AI-модели, "
        "какие технологии набирают обороты, а какие — тихо уходят со сцены."
    )
    humor = "Если ты пропустил всю неделю новостей — не страшно, зато у тебя всё в одном посте 😅"

    first_url = events[0].get("url") or ""

    return build_post_html(
        what=what_happened,
        why=why_important,
        source_url=first_url,
        humor=humor,
        hashtags="#НовостиIT #Digest #Дайджест",
    )
