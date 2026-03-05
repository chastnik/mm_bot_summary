# 🚀 Быстрый старт - Mattermost Summary Bot

🇬🇧 English version: [QUICKSTART_en.md](QUICKSTART_en.md)

## Минимальная установка (5 минут)

### 1. Скачивание
```bash
git clone <repository-url>
cd summary_bot
```

### 2. Установка зависимостей
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 3. Настройка
```bash
cp env.example .env
# Отредактируйте .env с вашими настройками
```

### 4. Запуск
```bash
python main.py
```

### 5. Проверка
- Откройте http://localhost:8080
- Добавьте бота в канал: `/invite @summary-bot`
- Используйте команду: `!summary`

## Основные настройки в .env

```bash
# Mattermost (ОБЯЗАТЕЛЬНО)
MATTERMOST_URL=https://your-server.com
MATTERMOST_TOKEN=your-bot-token

# LLM (LiteLLM / OpenAI-compatible)
LLM_PROXY_TOKEN=sk-your-token
LLM_BASE_URL=https://litellm.1bitai.ru
LLM_MODEL=gpt-5

# API токен для защищенных эндпоинтов
WEB_API_TOKEN=your-strong-random-token
```

## Команды бота

- `!summary` - создать саммари треда
- `summary` - простая команда
- `саммари` - русская команда
- `!саммари` - русская с восклицательным знаком

**⚠️ Важно:** Команды с `/` (например `/summary`) зарезервированы в Mattermost для слэш-команд. Используйте `!summary` или другие варианты.

## Мониторинг

- **Дашборд**: http://localhost:8080
- **Статус** (защищенный API): `curl -H "X-API-Token: $WEB_API_TOKEN" http://localhost:8080/status`
- **API**: http://localhost:8080/docs

---

**Готово! 🎉** Бот работает и готов создавать саммари ваших обсуждений. 