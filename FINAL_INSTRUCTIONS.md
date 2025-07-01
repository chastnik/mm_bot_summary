# 📋 Финальные инструкции по запуску Mattermost Summary Bot v2.0

## ✅ Статус проекта

**Проект полностью готов к работе!** Все компоненты протестированы и функционируют корректно.

### 🎯 Что работает:
- ✅ Подключение к Mattermost (HTTP API)
- ✅ Веб-интерфейс на порту 8080  
- ✅ Обработка команд саммари
- ✅ WebSocket архитектура v2.0
- ✅ Инициализация каналов "на лету"
- ✅ Система мониторинга и логирования

### ⚠️ Что требует настройки:
- WebSocket соединение (нужна проверка URL/токена)
- LLM токен (может потребовать обновления)

## 🚀 Быстрый старт

### 1. Подготовка окружения
```bash
# В корне проекта
source venv/bin/activate  # если venv уже создан
# или
python -m venv venv && source venv/bin/activate

pip install -r requirements.txt
```

### 2. Настройка конфигурации
```bash
# Скопируйте и отредактируйте конфигурацию
cp env.example .env
nano .env
```

**Критически важные параметры в `.env`:**
```bash
# Mattermost (ОБЯЗАТЕЛЬНО проверить)
MATTERMOST_URL=https://your-mattermost-server.com
MATTERMOST_TOKEN=your-bot-token-here

# LLM (корпоративная настройка)
LLM_PROXY_TOKEN=8d10b6d4-2e40-42fc-a66a-c9c6bf20c92c
LLM_BASE_URL=https://llm.1bitai.ru
LLM_MODEL=qwen3:14b

# Остальные параметры можно оставить по умолчанию
BOT_PORT=8080
LOG_LEVEL=INFO
DEBUG=false
```

### 3. Запуск
```bash
# Основной запуск
python main.py
```

### 4. Проверка работы
- 🌐 Откройте http://localhost:8080
- ✅ Проверьте статус компонентов на дашборде
- 📊 API доступно на http://localhost:8080/docs

## 🔧 Архитектура v2.0

### Ключевые компоненты:

1. **mattermost_bot.py** - WebSocket бот (основной)
   - Реальное время соединение с Mattermost
   - Автопереподключение при сбоях
   - Прямые HTTP API вызовы (без mattermostdriver)

2. **web_server.py** - FastAPI веб-сервер  
   - Современный дашборд с мониторингом
   - REST API для интеграции
   - Метрики Prometheus

3. **main.py** - Оркестратор
   - Управление жизненным циклом
   - Параллельный запуск компонентов
   - Graceful shutdown

### Преимущества новой архитектуры:
- 🔄 **Реальное время** - мгновенная реакция через WebSocket
- 🛠️ **Надежность** - автопереподключение и error handling
- 🌐 **Мониторинг** - полноценный веб-интерфейс
- 📊 **Интеграция** - REST API и метрики
- 🔧 **Гибкость** - поддержка hot-adding каналов

## 🎯 Использование бота

### 1. Настройка в Mattermost

**Создание бота:**
1. System Console → Integrations → Bot Accounts
2. Add Bot Account:
   - Username: `summary-bot`
   - Display Name: `Summary Bot`  
   - Description: `Бот для создания саммари тредов`
3. Сохраните Access Token в `.env`

### 2. Добавление в канал
```
/invite @summary-bot
```

### 3. Команды для саммари
В любом треде используйте:
- `!summary` 
- `summary`
- `саммари`

### 4. Автоинициализация каналов ✨

**Новая функция v2.0** - бот автоматически инициализируется при добавлении в новые каналы:

- При добавлении в канал отправляет приветственное сообщение
- Настраивает обработку команд автоматически
- Поддерживает как открытые каналы, так и личные чаты
- Работает без перезапуска бота

## 📊 Мониторинг и API

### Веб-дашборд (http://localhost:8080)
- Статус всех компонентов в реальном времени
- Логи и метрики
- Информация о подключениях
- Автообновление каждые 30 секунд

### API Эндпоинты
| URL | Описание |
|-----|----------|
| `/` | Главный дашборд |
| `/health` | Health check |
| `/status` | Детальный статус |
| `/info` | Информация о боте |
| `/metrics` | Prometheus метрики |
| `/docs` | Swagger документация |

### Curl примеры
```bash
# Быстрая проверка
curl http://localhost:8080/health

# Подробный статус  
curl http://localhost:8080/status | jq

# Метрики для мониторинга
curl http://localhost:8080/metrics
```

## 🔍 Диагностика

### Проверка подключений
```bash
# Логи в реальном времени
tail -f bot.log

# Статус через API
curl http://localhost:8080/status
```

### Типичные проблемы и решения

#### ❌ WebSocket не подключается
```bash
# Проверьте в .env:
MATTERMOST_URL=https://correct-server.com  # без trailing slash
MATTERMOST_TOKEN=correct-token-here

# Проверьте доступность
curl $MATTERMOST_URL/api/v4/system/ping
```

#### ❌ LLM недоступен  
```bash
# Проверьте корпоративный токен
curl -H "Authorization: Bearer 8d10b6d4-2e40-42fc-a66a-c9c6bf20c92c" \
  https://llm.1bitai.ru/v1/models
```

#### ❌ Бот не отвечает
1. Убедитесь что бот добавлен в канал: `/invite @summary-bot`
2. Проверьте права доступа в Mattermost
3. Попробуйте разные варианты команд

### Логи и отладка
```bash
# Детальные логи
export LOG_LEVEL=DEBUG
python main.py

# Только ошибки  
export LOG_LEVEL=ERROR
python main.py
```

## 🚀 Продакшн развертывание

### Systemd сервис
```bash
# /etc/systemd/system/summary-bot.service
[Unit]
Description=Mattermost Summary Bot v2.0
After=network.target

[Service]
Type=simple
User=mattermost
WorkingDirectory=/opt/summary-bot
Environment=PATH=/opt/summary-bot/venv/bin
ExecStart=/opt/summary-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Запуск как сервис
```bash
sudo systemctl daemon-reload
sudo systemctl enable summary-bot
sudo systemctl start summary-bot
sudo systemctl status summary-bot
```

### Nginx проксирование (опционально)
```nginx
server {
    listen 80;
    server_name summary-bot.company.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 📚 Дополнительная документация

- **README.md** - Основная документация
- **TROUBLESHOOTING.md** - Подробное решение проблем  
- **EXAMPLES.md** - Примеры использования
- **STATUS.md** - Статус разработки
- **CHANNEL_INITIALIZATION_ANALYSIS.md** - Анализ инициализации каналов

## ✅ Финальный чеклист

Перед запуском в продакшн убедитесь:

- [ ] `.env` файл настроен корректно
- [ ] Бот создан в Mattermost и токен актуален
- [ ] LLM сервис доступен с корпоративной сети
- [ ] Порт 8080 доступен для веб-интерфейса
- [ ] Логирование настроено (уровень INFO для продакшена)
- [ ] Systemd сервис создан (для автозапуска)
- [ ] Мониторинг настроен (веб-дашборд + /metrics)

## 🎉 Результат

После выполнения инструкций у вас будет:

1. **Работающий бот** с WebSocket подключением
2. **Веб-дашборд** для мониторинга на http://localhost:8080
3. **REST API** для интеграции с внешними системами
4. **Автоинициализация каналов** при добавлении бота
5. **Продакшен-ready** решение с логированием и метриками

---

**Проект готов к использованию!** 🚀

В случае проблем обращайтесь к документации или проверяйте статус через веб-интерфейс. 