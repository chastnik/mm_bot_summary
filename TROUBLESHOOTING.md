# 🔧 Устранение проблем

## Проблемы с зависимостями

### ModuleNotFoundError: No module named 'uvicorn'

**Решение:**
```bash
pip install -r requirements.txt
```

Если возникают конфликты зависимостей:
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Конфликты версий пакетов

**Причина:** Устаревшие зафиксированные версии в requirements.txt

**Решение:** Файл requirements.txt уже обновлен для использования совместимых версий:
```
mattermostdriver>=7.3.2
openai>=1.51.0
python-dotenv>=1.0.0
fastapi>=0.104.0
uvicorn>=0.24.0
requests>=2.31.0
typing-extensions>=4.11.0
```

## Проблемы с LLM соединением

### ❌ Ошибка: "Not allowed"

**Причина:** Проблемы с токеном или настройками LLM

**Проверьте:**
1. Актуальность токена LLM
2. Правильность URL сервиса
3. Доступность сервиса

**Обновите настройки в .env:**
```env
LLM_PROXY_TOKEN=your-actual-token
LLM_BASE_URL=https://your-llm-service.com
LLM_MODEL=your-model-name
```

### ❌ Ошибка: "Connection error"

**Причина:** Сетевые проблемы или недоступность сервиса

**Проверьте:**
```bash
# Проверка доступности
curl -I https://llm.1bitai.ru

# Тест с curl
curl -X POST https://llm.1bitai.ru/v1/chat/completions \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3:14b",
    "messages": [{"role": "user", "content": "test"}],
    "max_tokens": 10
  }'
```

## Проблемы с Mattermost

### ❌ Бот не отвечает на команды

**Проверьте:**
1. Бот добавлен в канал: `/invite @summary-bot`
2. Правильность токена в .env
3. Статус бота в Mattermost Admin Console

**Включите отладку:**
```env
DEBUG=true
```

### ❌ Ошибка подключения к Mattermost

**Ошибка DNS резолюции (Failed to resolve 'https'):**
- Проблема с парсингом URL в mattermostdriver
- Убедитесь что URL в правильном формате
- Проверьте доступность сервера: `ping your-mattermost.com`

**Проверьте .env файл:**
```env
MATTERMOST_URL=https://your-mattermost.com  # без / в конце
MATTERMOST_TOKEN=your-bot-token
```

**Создание бота в Mattermost:**
1. System Console → Integrations → Bot Accounts
2. Enable Bot Account Creation = True
3. Create Bot Account
4. Скопируйте Access Token

## Проблемы с Docker

### ❌ Контейнер не запускается

**Проверьте файл .env:**
```bash
# Убедитесь что файл существует
ls -la .env

# Проверьте содержимое
cat .env
```

**Пересоберите контейнер:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Просмотр логов:**
```bash
docker-compose logs -f summary-bot
```

## Общие проблемы

### ❌ Веб-интерфейс недоступен

**Проверьте:**
- Порт 8080 свободен: `netstat -tulpn | grep 8080`
- Настройки брандмауэра
- Запущен ли бот: `docker-compose ps`

### ❌ Бот создает неточные саммари

**Возможные причины:**
1. Проблемы с LLM сервисом
2. Слишком короткий тред (менее 3 сообщений)
3. Плохое качество исходных сообщений

**Решения:**
- Проверьте статус LLM: `curl http://localhost:8080/status`
- Используйте команду в содержательных тредах
- Перезапустите бота: `curl -X POST http://localhost:8080/restart`

## Команды для диагностики

### Проверка статуса
```bash
# Веб-интерфейс
curl http://localhost:8080/health

# Детальный статус
curl http://localhost:8080/status

# Логи
docker-compose logs -f summary-bot
```

### Тестирование компонентов
```bash
# Тест LLM
python test_llm.py

# Тест импортов
python -c "from main import *; print('OK')"

# Проверка зависимостей
pip check
```

### Сброс и очистка
```bash
# Остановка и удаление контейнеров
docker-compose down --volumes

# Удаление образов
docker image prune -a

# Переустановка зависимостей
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

## Поддержка

Если проблемы не решаются:

1. **Соберите информацию:**
   - Логи: `docker-compose logs summary-bot > bot-logs.txt`
   - Конфигурация: `cat .env` (без токенов!)
   - Версия Python: `python --version`
   - Статус: `curl http://localhost:8080/status`

2. **Проверьте известные проблемы** в Issues репозитория

3. **Создайте новый Issue** с собранной информацией 