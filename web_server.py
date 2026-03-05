#!/usr/bin/env python3
"""
Веб-сервер для Mattermost Summary Bot
Предоставляет веб-интерфейс для мониторинга состояния бота
"""

from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse
from config import Config

def create_app(bot) -> FastAPI:
    """Создает FastAPI приложение с переданным ботом"""
    
    app = FastAPI(
        title="Mattermost Summary Bot",
        description="Бот для создания саммари тредов в Mattermost",
        version="2.0.0"
    )

    def _verify_api_token(x_api_token: Optional[str] = Header(default=None)) -> None:
        """Проверка токена для внутренних API-эндпоинтов."""
        if not Config.WEB_API_TOKEN:
            raise HTTPException(
                status_code=503,
                detail="WEB_API_TOKEN не настроен. Установите токен в окружении.",
            )
        if x_api_token != Config.WEB_API_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid API token")
    
    def _generate_subscriptions_html(subscriptions_info):
        """Генерирует HTML для отображения подписок"""
        if not subscriptions_info:
            return "<div style='text-align: center; color: #666; padding: 20px;'>Нет активных подписок</div>"
        
        html_parts = []
        
        for sub in subscriptions_info:
            channels = ", ".join(sub['channels'])
            freq_text = "ежедневно" if sub['frequency'] == 'daily' else "еженедельно"
            
            # Добавляем день недели для еженедельных подписок
            weekday_text = ""
            if sub['frequency'] == 'weekly' and sub.get('weekday') is not None:
                weekday_names = ['понедельникам', 'вторникам', 'средам', 'четвергам', 'пятницам', 'субботам', 'воскресеньям']
                weekday_text = f" по {weekday_names[sub['weekday']]}"
            
            html_parts.append(f"""
            <div style="background: #f8f9fa; border-radius: 8px; padding: 15px; margin: 10px 0; border-left: 4px solid #28a745;">
                <div style="font-weight: bold; color: #333; margin-bottom: 8px;">
                    👤 {sub['username']}
                </div>
                <div style="color: #666; margin-bottom: 5px;">
                    📢 Каналы: {channels}
                </div>
                <div style="color: #666; margin-bottom: 5px;">
                    ⏰ Время: {sub['schedule_time']} ({freq_text}{weekday_text})
                </div>
                <div style="color: #999; font-size: 0.9em;">
                    📅 Создано: {sub['created_at'][:10]}
                </div>
            </div>
            """)
        
        return "".join(html_parts)
    
    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Главная страница с дашбордом"""
        try:
            status = await bot.health_check()
            
            # Получаем информацию о подписках
            subscriptions_info = bot.subscription_manager.get_all_subscriptions()
            total_subscriptions = len(subscriptions_info)
            
            # Определяем статусы для отображения
            mattermost_status = "🟢 Подключен" if status.get('mattermost_connected') else "🔴 Отключен"
            llm_status = "🟢 Подключен" if status.get('llm_connected') else "🔴 Отключен" 
            bot_status = "🟢 Работает" if status.get('bot_running') else "🔴 Остановлен"
            websocket_status = "🟢 Подключен" if status.get('websocket_connected') else "🔴 Отключен"
            
            return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mattermost Summary Bot</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .content {{
            padding: 30px;
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .status-card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #007bff;
            transition: transform 0.2s;
        }}
        .status-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        .status-card h3 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 1.1em;
        }}
        .status-value {{
            font-size: 1.2em;
            font-weight: 500;
        }}
        .instructions {{
            background: #e7f3ff;
            border-radius: 10px;
            padding: 25px;
            margin: 20px 0;
            border-left: 4px solid #0066cc;
        }}
        .instructions h3 {{
            color: #0066cc;
            margin-top: 0;
        }}
        .code {{
            background: #2d3748;
            color: #e2e8f0;
            padding: 3px 8px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        .api-links {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        .api-link {{
            display: block;
            padding: 15px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            text-align: center;
            transition: background 0.2s;
        }}
        .api-link:hover {{
            background: #0056b3;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #dee2e6;
        }}
        .timestamp {{
            color: #999;
            font-size: 0.9em;
            margin-top: 20px;
        }}
        @media (max-width: 768px) {{
            .container {{
                margin: 10px;
                border-radius: 10px;
            }}
            .header {{
                padding: 20px;
            }}
            .header h1 {{
                font-size: 2em;
            }}
            .content {{
                padding: 20px;
            }}
            .status-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Mattermost Summary Bot</h1>
            <p>Система создания саммари тредов с помощью ИИ</p>
        </div>
        
        <div class="content">
            <div class="status-grid">
                <div class="status-card">
                    <h3>🤖 Статус бота</h3>
                    <div class="status-value">{bot_status}</div>
                </div>
                <div class="status-card">
                    <h3>💬 Mattermost</h3>
                    <div class="status-value">{mattermost_status}</div>
                </div>
                <div class="status-card">
                    <h3>🔌 WebSocket</h3>
                    <div class="status-value">{websocket_status}</div>
                </div>
                <div class="status-card">
                    <h3>🧠 LLM</h3>
                    <div class="status-value">{llm_status}</div>
                </div>
                <div class="status-card">
                    <h3>📊 Подписки</h3>
                    <div class="status-value">{total_subscriptions} активных</div>
                </div>
            </div>
            
            <div class="instructions">
                <h3>📊 Активные подписки</h3>
                {_generate_subscriptions_html(subscriptions_info)}
            </div>
            
            <div class="instructions">
                <h3>📋 Инструкции по использованию</h3>
                <p><strong>Как использовать:</strong></p>
                <ol>
                    <li>Добавьте бота в канал: <span class="code">/invite @summary_bot</span></li>
                    <li>В треде используйте команду: <span class="code">!summary</span>, <span class="code">summary</span>, <span class="code">саммари</span>, <span class="code">!саммари</span></li>
                    <li>Подождите несколько секунд - бот создаст саммари треда</li>
                    <li>Получите структурированное резюме обсуждения!</li>
                </ol>
                
                <p><strong>Команды в каналах:</strong></p>
                <ul>
                    <li><span class="code">!summary</span> - основная команда</li>
                    <li><span class="code">summary</span> - простая команда</li>
                    <li><span class="code">саммари</span> - на русском языке</li>
                    <li><span class="code">!саммари</span> - русская с восклицательным знаком</li>
                </ul>
                
                <p><strong>Подписки на каналы:</strong></p>
                <ol>
                    <li>Напишите боту в личное сообщение</li>
                    <li>Создайте подписку в формате: <span class="code">general,random ~ 09:00 ~ daily</span></li>
                    <li>Получайте сводки в личные сообщения по расписанию</li>
                </ol>
                
                <p><strong>Команды управления подписками (в личных сообщениях):</strong></p>
                <ul>
                    <li><span class="code">подписки</span> - посмотреть текущие подписки</li>
                    <li><span class="code">удалить подписку</span> - удалить все подписки</li>
                    <li><span class="code">создать подписку</span> - получить инструкцию</li>
                </ul>
                
                <div class="warning" style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <strong>⚠️ Важно:</strong> Команды с <code>/</code> (например <code>/summary</code>) зарезервированы в Mattermost для системных слэш-команд. Используйте команды с <code>!</code> или без символов.
                </div>
            </div>
            
            <div class="instructions">
                <h3>🔧 API Эндпоинты</h3>
                <div class="api-links">
                    <a href="/health" class="api-link">
                        ❤️ Health Check
                    </a>
                    <a href="/status" class="api-link">
                        📊 Подробный статус
                    </a>
                    <a href="/info" class="api-link">
                        ℹ️ Информация о боте
                    </a>
                    <a href="/subscriptions" class="api-link">
                        📊 Подписки (JSON)
                    </a>
                    <a href="/docs" class="api-link">
                        📚 API Документация
                    </a>
                </div>
            </div>
            
            <div class="timestamp">
                Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
            </div>
        </div>
        
        <div class="footer">
            <p>Mattermost Summary Bot v2.0 | Создано для автоматизации работы с тредами</p>
        </div>
    </div>
    
    <script>
        // Автообновление страницы каждые 30 секунд
        setTimeout(() => {{
            location.reload();
        }}, 30000);
    </script>
</body>
</html>"""
            
        except Exception as e:
            return f"""
<!DOCTYPE html>
<html>
<head><title>Ошибка</title></head>
<body>
    <h1>❌ Ошибка загрузки дашборда</h1>
    <p>Произошла ошибка: {str(e)}</p>
    <a href="/">Попробовать снова</a>
</body>
</html>"""
    
    @app.get("/health")
    async def health_check():
        """Проверка здоровья бота"""
        try:
            status = await bot.health_check()
            
            if status.get('mattermost_connected') and status.get('bot_running'):
                return {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "details": status
                }
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "timestamp": datetime.now().isoformat(),
                        "details": status
                    }
                )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    @app.get("/status")
    async def detailed_status(x_api_token: Optional[str] = Header(default=None)):
        """Подробный статус всех компонентов"""
        try:
            _verify_api_token(x_api_token)
            status = await bot.health_check()
            return {
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "bot": {
                        "running": status.get('bot_running', False),
                        "username": status.get('bot_username'),
                        "user_id": status.get('bot_user_id')
                    },
                    "mattermost": {
                        "connected": status.get('mattermost_connected', False),
                        "websocket": status.get('websocket_connected', False)
                    },
                    "llm": {
                        "connected": status.get('llm_connected', False)
                    }
                },
                "overall_status": "healthy" if all([
                    status.get('bot_running'),
                    status.get('mattermost_connected')
                ]) else "degraded"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/info")
    async def bot_info(x_api_token: Optional[str] = Header(default=None)):
        """Информация о боте"""
        try:
            _verify_api_token(x_api_token)
            status = await bot.health_check()
            return {
                "name": "Mattermost Summary Bot",
                "version": "2.0.0",
                "description": "Бот для создания саммари тредов в Mattermost с помощью LLM",
                "features": [
                    "Создание саммари тредов",
                    "WebSocket подключение в реальном времени",
                    "Поддержка различных команд",
                    "Веб-интерфейс для мониторинга",
                    "REST API для интеграции"
                ],
                "supported_commands": [
                    "!summary",
                    "summary", 
                    "саммари",
                    "!саммари"
                ],
                "bot_info": {
                    "username": status.get('bot_username'),
                    "user_id": status.get('bot_user_id'),
                    "running": status.get('bot_running', False)
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/subscriptions")
    async def subscriptions(x_api_token: Optional[str] = Header(default=None)):
        """Получение информации о подписках"""
        try:
            _verify_api_token(x_api_token)
            all_subscriptions = bot.subscription_manager.get_all_subscriptions()
            
            return {
                "total_subscriptions": len(all_subscriptions),
                "subscriptions": all_subscriptions,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/metrics")
    async def metrics(x_api_token: Optional[str] = Header(default=None)):
        """Метрики для мониторинга"""
        try:
            _verify_api_token(x_api_token)
            status = await bot.health_check()
            
            # Получаем информацию о подписках
            subscriptions_count = len(bot.subscription_manager.get_all_subscriptions())
            
            # Простые метрики в формате, совместимом с Prometheus
            metrics = []
            metrics.append(f"mattermost_bot_running {1 if status.get('bot_running') else 0}")
            metrics.append(f"mattermost_connected {1 if status.get('mattermost_connected') else 0}")
            metrics.append(f"websocket_connected {1 if status.get('websocket_connected') else 0}")
            metrics.append(f"llm_connected {1 if status.get('llm_connected') else 0}")
            metrics.append(f"total_subscriptions {subscriptions_count}")
            
            return "\n".join(metrics)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return app 