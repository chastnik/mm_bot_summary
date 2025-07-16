# 🤖 Mattermost Summary Bot v2.4

Умный бот для автоматического создания саммари тредов в Mattermost с использованием корпоративной LLM и поддержкой подписок на каналы.

## ✨ Особенности v2.4

- 📊 **Подписки на каналы** - регулярные сводки активности в личные сообщения
- 📱 **Личные сообщения** - управление подписками через DM с ботом
- ⏰ **Планировщик задач** - автоматическая доставка сводок по расписанию
- 🔄 **WebSocket соединение в реальном времени** - мгновенная реакция на команды
- 🎯 **Надежная архитектура** - основанная на лучших практиках Mattermost ботов  
- 💬 **Прямые HTTP запросы** - избегание проблем с mattermostdriver
- 🌐 **Улучшенный веб-интерфейс** - современный дашборд для мониторинга
- 🛠️ **REST API** - полноценное API для интеграции и мониторинга
- 🔧 **Автопереподключение** - устойчивость к сбоям сети
- 📊 **Метрики Prometheus** - готовность к продакшену
- 💾 **База данных SQLite** - хранение подписок и логов доставки

## 🚀 Функциональность

### Основные возможности
- **Саммари тредов:** Создание структурированных саммари по командам `!summary`, `summary`, `саммари`, `!саммари`
- **Подписки на каналы:** Регулярные сводки активности в указанных каналах
- **Личные сообщения:** Управление подписками через DM с ботом
- **Автоматическая доставка:** Сводки по расписанию (ежедневно/еженедельно)
- **Проверка доступа:** Уведомления о недоступных каналах
- **Веб-интерфейс:** Мониторинг состояния бота и подписок
- **REST API:** Интеграция с внешними системами

### Формат саммари
Бот создает структурированные саммари, включающие:
- 👥 **Участники обсуждения**
- 💬 **Основные темы**  
- 📋 **Ключевые моменты**
- ✅ **Задачи и действия**
- 🎯 **Выводы и итоги**

## 🏗️ Архитектура

```mermaid
graph TD
    A[Mattermost Chat] -->|WebSocket| B[Summary Bot]
    B -->|HTTP API| C[LLM Service]
    B -->|FastAPI| D[Web Dashboard]
    B -->|REST API| E[External Systems]
    B -->|SQLite| F[Subscription Database]
    
    subgraph "Bot Components"
        G[WebSocket Handler]
        H[Message Processor] 
        I[Summary Generator]
        J[Health Monitor]
        K[Subscription Manager]
        L[Subscription Scheduler]
        M[DM Handler]
    end
    
    B --> G
    G --> H
    H --> I
    I --> C
    B --> J
    J --> D
    B --> K
    K --> F
    B --> L
    L --> K
    B --> M
    M --> K
```

### 📋 Поток обработки команд саммари

```mermaid
sequenceDiagram
    participant User as 👤 Пользователь
    participant MM as 📱 Mattermost
    participant Bot as 🤖 Bot
    participant LLM as 🧠 LLM Service
    
    User->>MM: Пишет "!summary" в треде
    MM->>Bot: WebSocket событие
    Bot->>Bot: Проверка команды
    Bot->>MM: Получение сообщений треда
    MM->>Bot: Данные треда
    Bot->>LLM: Запрос саммари
    LLM->>Bot: Структурированный ответ
    Bot->>MM: Отправка саммари
    MM->>User: Показ саммари
```

### 📊 Система подписок

```mermaid
flowchart TD
    A[👤 Пользователь] -->|DM боту| B[📱 Обработка команды]
    B --> C{Тип команды?}
    
    C -->|Создание подписки| D[🔍 Парсинг каналов/времени]
    C -->|Просмотр подписок| E[📋 Показ списка]
    C -->|Удаление подписки| F[🗑️ Удаление]
    
    D --> G[💾 Сохранение в БД]
    G --> H[✅ Подтверждение]
    
    subgraph "Планировщик"
        I[⏰ Проверка каждую минуту]
        I --> J{Время подписки?}
        J -->|Да| K[📊 Сбор сообщений]
        J -->|Нет| I
        K --> L[🧠 Генерация сводки]
        L --> M[📨 Отправка в DM]
        M --> I
    end
    
    G --> I
```

### 🏗️ Структура компонентов

```mermaid
classDiagram
    class MattermostBot {
        +initialize()
        +start_listening()
        +handle_message()
        +send_summary()
        -_connect_websocket()
        -_handle_post_event()
        -_handle_direct_message()
    }
    
    class SubscriptionManager {
        +create_subscription()
        +get_user_subscriptions()
        +delete_subscription()
        +check_channel_access()
        -_init_database()
    }
    
    class SubscriptionScheduler {
        +start()
        +stop()
        -_scheduler_loop()
        -_execute_subscription()
        -_should_execute_subscription()
    }
    
    class LLMClient {
        +generate_summary()
        +generate_channels_summary()
        +test_connection()
        -_make_request()
    }
    
    class WebServer {
        +create_app()
        +health_check()
        +status_check()
        +subscriptions_info()
    }
    
    class BotApplication {
        +start()
        +shutdown()
        -_run_bot()
        -_run_web_server()
    }
    
    BotApplication --> MattermostBot
    BotApplication --> SubscriptionScheduler
    BotApplication --> WebServer
    MattermostBot --> SubscriptionManager
    MattermostBot --> LLMClient
    SubscriptionScheduler --> SubscriptionManager
    SubscriptionScheduler --> MattermostBot
    WebServer --> MattermostBot
```

### 🔄 Жизненный цикл бота

```mermaid
stateDiagram-v2
    [*] --> Initializing
    
    Initializing --> Connecting : Config OK
    Initializing --> Error : Config Error
    
    Connecting --> Connected : WebSocket OK
    Connecting --> Reconnecting : Connection Failed
    
    Connected --> Listening : Ready
    Listening --> Processing : Message Received
    Processing --> Listening : Response Sent
    
    Listening --> Reconnecting : Connection Lost
    Reconnecting --> Connected : Reconnected
    Reconnecting --> Error : Max Retries
    
    Connected --> Scheduling : Subscriptions Active
    Scheduling --> Delivering : Time Match
    Delivering --> Scheduling : Summary Sent
    
    Listening --> Shutdown : Stop Signal
    Scheduling --> Shutdown : Stop Signal
    Processing --> Shutdown : Stop Signal
    
    Shutdown --> [*]
    Error --> [*]
    
    note right of Processing
        Обработка команд:
        - !summary
        - Создание подписок
        - Управление подписками
    end note
    
    note right of Delivering
        Автоматическая доставка:
        - Проверка расписания
        - Сбор сообщений
        - Генерация сводки
        - Отправка в DM
    end note
```

## 🛠️ Установка и настройка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd summary_bot
```

### 2. Создание виртуального окружения
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка конфигурации

Создайте файл `.env` на основе `env.example`:

```bash
cp env.example .env
```

Отредактируйте `.env`:

```bash
# Mattermost настройки
MATTERMOST_URL=https://your-mattermost-server.com
MATTERMOST_TOKEN=your-bot-token-here

# LLM настройки (корпоративная LLM)
LLM_PROXY_TOKEN=token
LLM_BASE_URL=llm_url
LLM_MODEL=model_name

# Настройки бота
BOT_PORT=8080
LOG_LEVEL=INFO
DEBUG=false
```

### 5. Создание бота в Mattermost

1. Войдите в Mattermost как администратор
2. Перейдите в **System Console → Integrations → Bot Accounts**
3. Нажмите **Add Bot Account**
4. Заполните форму:
   - **Username**: `summary-bot`
   - **Display Name**: `Summary Bot`
   - **Description**: `Бот для создания саммари тредов`
5. Сохраните **Access Token** в `.env` файл

## 🏃‍♂️ Запуск

### Основной запуск
```bash
python main.py
```

После запуска:
- 🌐 **Веб-интерфейс**: http://localhost:8080
- 📊 **Статус**: http://localhost:8080/status  
- ❤️ **Health Check**: http://localhost:8080/health
- 📚 **API Документация**: http://localhost:8080/docs

## 💬 Использование

### 📋 Саммари тредов в каналах

#### 1. Добавление бота в канал
```
/invite @summary-bot
```

#### 2. Создание саммари
В любом треде напишите одну из команд:
- `!summary` - основная команда
- `summary` - простая команда
- `саммари` - на русском языке
- `!саммари` - русская с восклицательным знаком

**⚠️ Важно:** Команды с `/` (например `/summary`) зарезервированы в Mattermost для системных слэш-команд. Используйте команды с `!` или без символов.

#### 3. Получение результата
Бот создаст структурированное саммари треда с анализом обсуждения.

### 📊 Подписки на каналы

#### 1. Первое обращение к боту
Напишите боту **любое сообщение** в личку - он ответит подробной инструкцией.

#### 2. Создание подписки
Отправьте сообщение в естественном формате:

**Поддерживаемые форматы:**
```
~канал1, ~канал2 ежедневно в 9 утра
~канал1, ~канал2 еженедельно по вторникам в 18:00
~канал1 каждую среду в 6 вечера
~канал1 вторник 18:00
~канал1 пятница 17:30
```

**Примеры:**
```
~general, ~random ежедневно в 9 утра
~development, ~qa еженедельно по вторникам в 18:00
~marketing каждую пятницу в 15:30
~support понедельник в 10:00
~sales четверг 14:00
```

**Периодичность:**
• `ежедневно` или `каждый день`
• `еженедельно` или `каждую неделю`
• `каждую среду` или `каждый понедельник`
• Просто `вторник`, `среда`, `пятница` и т.д.

**Время:**
• `в 9 утра` или `в 09:00`
• `в 18:00` или `в 6 вечера`
• `в 15:30` или просто `18:00`

**Дни недели (для еженедельных подписок):**
• `по понедельникам`, `по вторникам`, `по средам`, `по четвергам`
• `по пятницам`, `по субботам`, `по воскресеньям`
• `каждую среду`, `каждый понедельник`, `каждую пятницу`
• Просто `понедельник`, `вторник`, `среда`, `четверг`, `пятница`, `суббота`, `воскресенье`

💡 **Важно:** В Mattermost символ `~` необходим для выбора канала!

#### 3. Управление подписками
- `подписки` - посмотреть текущие подписки
- `удалить подписку` - удалить все подписки
- `создать подписку` - получить инструкцию

#### 4. Получение сводок
Сводки будут автоматически приходить в личные сообщения в указанное время.

📖 **Подробная документация:** [SUBSCRIPTIONS.md](./SUBSCRIPTIONS.md)

## 🔧 API Эндпоинты

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/` | GET | Веб-дашборд |
| `/health` | GET | Проверка здоровья |
| `/status` | GET | Подробный статус |
| `/info` | GET | Информация о боте |
| `/subscriptions` | GET | Информация о подписках |
| `/metrics` | GET | Метрики Prometheus |
| `/docs` | GET | API документация |

### Примеры запросов

#### Проверка здоровья
```bash
curl http://localhost:8080/health
```

#### Статус компонентов
```bash
curl http://localhost:8080/status
```

#### Метрики для мониторинга
```bash
curl http://localhost:8080/metrics
```

## 🔍 Мониторинг и диагностика

### Логи
```bash
# Просмотр логов
tail -f bot.log

# Мониторинг в реальном времени
python main.py
```

### Статус компонентов
- ✅ **Mattermost**: подключение к серверу
- ✅ **WebSocket**: реальное время соединение  
- ✅ **LLM**: доступность AI сервиса
- ✅ **Bot**: состояние основного процесса

### Диагностика проблем

#### WebSocket не подключается
1. Проверьте URL и токен Mattermost в `.env`
2. Убедитесь в доступности сервера
3. Проверьте сетевую связность

#### LLM недоступен
1. Обновите `LLM_PROXY_TOKEN` в `.env`
2. Проверьте доступность https://llm.1bitai.ru
3. Проверьте корпоративные сетевые настройки

#### Бот не отвечает на команды
1. Убедитесь что бот добавлен в канал
2. Проверьте права доступа бота
3. Попробуйте разные варианты команд

## 🔧 Разработка

### Тестирование конфигурации
```bash
python config.py
```

### Структура проекта
```
summary_bot/
├── main.py              # Основная точка входа
├── mattermost_bot.py    # WebSocket бот (v2.4)
├── config.py           # Управление конфигурацией
├── llm_client.py       # LLM интеграция
├── web_server.py       # FastAPI веб-сервер
├── requirements.txt    # Python зависимости
├── env.example        # Пример конфигурации
└── README.md          # Документация
```

### Ключевые улучшения

1. **WebSocket вместо HTTP polling** - мгновенная реакция
2. **Прямые HTTP запросы** - избежание проблем парсинга URL  
3. **Улучшенная обработка ошибок** - автопереподключение
4. **Современный веб-интерфейс** - адаптивный дизайн
5. **Расширенное API** - готовность к интеграции
6. **Метрики мониторинга** - продакшен ready
7. **Естественные форматы подписок** - поддержка команд типа "каждую среду в 6 вечера"

## 🚀 Деплой в продакшен

### Systemd сервис
```bash
# Создание сервиса
sudo nano /etc/systemd/system/summary-bot.service

# Содержимое файла:
[Unit]
Description=Mattermost Summary Bot
After=network.target

[Service]
Type=simple
User=summary-bot
WorkingDirectory=/opt/summary-bot
Environment=PATH=/opt/summary-bot/venv/bin
ExecStart=/opt/summary-bot/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target

# Активация
sudo systemctl daemon-reload
sudo systemctl enable summary-bot
sudo systemctl start summary-bot
```

### Nginx прокси (опционально)
```nginx
server {
    listen 80;
    server_name summary-bot.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📋 Требования

- Python 3.8+
- Mattermost Server 5.0+
- Доступ к корпоративной LLM
- Токен бота Mattermost

## 📄 Лицензия

MIT License

## 🤝 Поддержка

При возникновении проблем:

1. Проверьте статус на веб-дашборде
2. Изучите логи приложения
3. Убедитесь в правильности конфигурации
4. Проверьте сетевую доступность сервисов

---

**v2.4** - Добавлена расширенная поддержка естественных форматов времени и дней недели для подписок. Теперь поддерживаются команды типа "каждую среду в 6 вечера" и "вторник 18:00". 