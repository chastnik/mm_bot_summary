FROM python:3.11-slim

LABEL maintainer="Mattermost Summary Bot" \
      description="AI-powered Mattermost bot for channel summaries and subscriptions"

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .

# Обновляем pip и устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем пользователя для запуска приложения
RUN useradd --create-home --shell /bin/bash bot && \
    chown -R bot:bot /app

# Переключаемся на пользователя bot
USER bot

# Создаем директорию для данных
RUN mkdir -p /app/data

# Экспортируем порт
EXPOSE 8080

# Healthcheck для проверки состояния контейнера
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Запускаем приложение
CMD ["python", "main.py"] 