# 🚀 Быстрый старт

## 1. Настройка конфигурации

Создайте файл `.env`:

```bash
# Скопируйте шаблон
cp env.example .env

# Отредактируйте настройки Mattermost
nano .env
```

Заполните обязательные поля:
```env
MATTERMOST_URL=https://your-mattermost-instance.com
MATTERMOST_TOKEN=your-bot-token
```

**LLM настройки уже предустановлены!**

## 2. Создание бота в Mattermost

1. **System Console** → **Integrations** → **Bot Accounts**
2. **Enable Bot Account Creation** = True
3. **Create Bot Account**:
   - Username: `summary-bot`
   - Display Name: `Summary Bot`
   - Description: `Бот для создания саммари тредов`
4. **Скопируйте токен** в файл `.env`

## 3. Запуск

### Простой способ:
```bash
./start.sh
```

### Docker:
```bash
docker-compose up -d
```

### Python:
```bash
pip install -r requirements.txt
python main.py
```

## 4. Проверка

- **Веб-интерфейс**: http://localhost:8080
- **Тест LLM**: `python test_llm.py`
- **Статус**: `curl http://localhost:8080/health`

## 5. Использование

1. Добавьте бота в канал: `/invite @summary-bot`
2. В треде напишите: `/summary`
3. Получите саммари! 🎉

## Поддерживаемые команды:
- `/summary` 
- `!summary`
- `/саммари`
- `summary`

## Устранение проблем:

```bash
# Логи Docker
docker-compose logs -f summary-bot

# Перезапуск
docker-compose restart summary-bot

# Проверка статуса
curl http://localhost:8080/status
``` 