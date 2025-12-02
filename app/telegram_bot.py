# app/telegram_bot.py
from typing import Optional, Tuple, List, Dict

from telegram import Bot
from telegram.error import TelegramError

from .text_utils import truncate_message
from .logging_utils import log_error

def split_title_and_body(content: str) -> Tuple[str, str]:
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        return "Свежая новость из мира IT", ""

    title = lines[0][:200]  # режем на всякий случай
    body = " ".join(lines[1:])[:800]  # короткий анонс
    return title, body


def format_news_message(
    url: str,
    content: str,
    topic_tag: str = "#AI",
    source_tag: str = "#НовостиIT",
) -> str:
    title, body = split_title_and_body(content)

    what_happened = f"{title}\n\n{body}" if body else title
    why_important = (
        "Это часть свежих изменений в мире IT и AI — полезно, чтобы не отставать от трендов."
    )
    humor = "Похоже, новости обновляются быстрее, чем наши пет-проекты в GitHub 😅"

    message = (
        f"💡 Что произошло: {what_happened}\n\n"
        f"📌 Почему это важно: {why_important}\n\n"
        f"🔗 Источник: {url}\n\n"
        f"😅 Юмор: {humor}\n\n"
        f"#НовостиIT {topic_tag} {source_tag}"
    )
    return message


def send_message(bot_token: str, chat_id: str, text: str) -> Optional[str]:
    """
    Отправка сообщения в Telegram с учётом лимита 4096 символов.
    - текст сначала обрезается через truncate_message
    - ошибки логируются и дублируются алертом
    """
    bot = Bot(token=bot_token)

    # Ограничиваем длину сообщения под лимит Telegram
    text = truncate_message(text)

    try:
        msg = bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        return str(msg.message_id)
    except TelegramError as e:
        log_error(f"Ошибка отправки сообщения в Telegram: {e}", alert=True)
        return None

def format_tools_digest_message(tools: List[Dict]) -> str:
    """
    Формат субботней подборки тулзов.
    tools: список словарей {title, summary, url, use_case, source_tag}
    """
    lines = []
    lines.append("Сегодня собрал для тебя подборку свежих тулзов и сервисов для разработчиков 👇\n")

    for idx, tool in enumerate(tools, start=1):
        title = tool.get("title") or "Новый инструмент"
        summary = tool.get("summary") or ""
        url = tool.get("url") or ""
        use_case = tool.get("use_case") or "Поможет упростить жизнь разработчику."
        source_tag = tool.get("source_tag") or "#Tools"

        block = (
            f"{idx}) **{title}** {source_tag}\n"
            f"   {summary}\n"
            f"   Юзкейс: {use_case}\n"
            f"   🔗 {url}\n"
        )
        lines.append(block)

    what_happened = "\n".join(lines).strip()

    why_important = (
        "Такие инструменты экономят время, снижают рутину и помогают сосредоточиться на фичах, "
        "а не на настройке окружения."
    )
    humor = "Главное — не поставить все тулзы сразу и не провести выходные в конфигурации docker-compose 😅"

    message = (
        f"💡 Что произошло: {what_happened}\n\n"
        f"📌 Почему это важно: {why_important}\n\n"
        f"🔗 Источник: ссылки на каждую тулзу в списке выше.\n\n"
        f"😅 Юмор: {humor}\n\n"
        f"#НовостиIT #Tools #Подборка"
    )
    return message


def format_weekly_digest_message(events: List[Dict]) -> str:
    """
    Формат воскресного дайджеста недели.
    events: список {title, summary, url, source_tag}
    """
    if not events:
        return (
            "💡 Что произошло: На этой неделе громких новостей почти не было, "
            "но это отличный шанс догнать свои пет-проекты.\n\n"
            "📌 Почему это важно: даже тишина в новостях — сигнал, что можно спокойно поучиться и поэкспериментировать.\n\n"
            "🔗 Источник: —\n\n"
            "😅 Юмор: Иногда лучший релиз — это отпуск от новостной ленты 😅\n\n"
            "#НовостиIT #Digest #Дайджест"
        )

    intro = (
        "За прошедшую неделю в мире IT и AI произошло несколько важных событий. "
        "Вот краткий дайджест, чтобы не рыться в ленте весь день 👇\n"
    )

    blocks = []
    for idx, ev in enumerate(events, start=1):
        title = ev.get("title") or "Событие недели"
        summary = ev.get("summary") or ""
        url = ev.get("url") or ""
        source_tag = ev.get("source_tag") or "#НовостиIT"

        block = (
            f"{idx}) **{title}** {source_tag}\n"
            f"   {summary}\n"
            f"   🔗 {url}\n"
        )
        blocks.append(block)

    what_happened = intro + "\n".join(blocks)

    why_important = (
        "Такой срез по неделе помогает видеть общие тренды: куда двигаются AI-модели, "
        "какие технологии набирают обороты, а какие — тихо уходят со сцены."
    )
    humor = "Если ты пропустил всю неделю новостей — не страшно, зато у тебя всё в одном посте 😅"

    message = (
        f"💡 Что произошло: {what_happened}\n\n"
        f"📌 Почему это важно: {why_important}\n\n"
        f"🔗 Источник: ссылки на каждое событие в списке выше.\n\n"
        f"😅 Юмор: {humor}\n\n"
        f"#НовостиIT #Digest #Дайджест"
    )
    return message