FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Базовые утилиты для сборки пакетов (lxml / sklearn и т.п.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем только код приложения
COPY app ./app

# По умолчанию запускаем планировщик (ежедневные новости в 09:00 МСК)
CMD ["python", "-m", "app.scheduler_main"]
