#!/usr/bin/env python3
"""
Автономная версия Mattermost Summary Bot

Использует прямые HTTP запросы вместо mattermostdriver для избежания проблем с парсингом URL.
"""

import asyncio
import logging
import json
import sys
import requests
import time
from typing import List, Dict, Any, Optional
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from config import Config
from llm_client import LLMClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class SimpleMattermostBot:
    """Упрощенная версия бота с прямыми HTTP запросами"""
    
    def __init__(self):
        self.base_url = None
        self.token = None
        self.bot_user_id = None
        self.llm_client = LLMClient()
        self._running = False
        
    async def initialize(self):
        """Инициализация бота"""
        try:
            # Подготавливаем URL
            self.base_url = Config.MATTERMOST_URL.strip().rstrip('/')
            if not self.base_url.startswith(('http://', 'https://')):
                self.base_url = 'https://' + self.base_url
            
            self.token = Config.MATTERMOST_TOKEN
            
            # Проверяем подключение
            headers = {'Authorization': f'Bearer {self.token}'}
            response = requests.get(f"{self.base_url}/api/v4/users/me", 
                                  headers=headers, timeout=10, verify=False)
            
            if response.status_code == 200:
                user_data = response.json()
                self.bot_user_id = user_data['id']
                logger.info(f"Бот подключен как {user_data['username']} (ID: {self.bot_user_id})")
                return True
            else:
                logger.error(f"Ошибка аутентификации: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}")
            return False
    
    async def health_check(self):
        """Проверка состояния бота"""
        return {
            'mattermost_connected': self.bot_user_id is not None,
            'llm_connected': await self.llm_client.test_connection(),
            'bot_running': self._running,
            'mode': 'standalone'
        }
    
    def send_message(self, channel_id: str, message: str, root_id: Optional[str] = None):
        """Отправка сообщения"""
        try:
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            post_data = {
                'channel_id': channel_id,
                'message': message
            }
            
            if root_id:
                post_data['root_id'] = root_id
            
            response = requests.post(f"{self.base_url}/api/v4/posts", 
                                   headers=headers, 
                                   json=post_data, 
                                   timeout=10, 
                                   verify=False)
            
            if response.status_code == 201:
                logger.info("Сообщение отправлено успешно")
            else:
                logger.error(f"Ошибка отправки сообщения: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
    
    def demo_summary(self):
        """Демо-саммари для тестирования"""
        return """## 📝 Саммари треда (ДЕМО)

**👥 Участники обсуждения:**
alice, bob, charlie

**💬 Основные темы обсуждения:**
Тестирование работы бота создания саммари

**📋 Ключевые моменты:**
• Бот успешно подключился к Mattermost
• Веб-интерфейс работает корректно
• LLM интеграция настроена

**✅ Задачи и действия:**
• Протестировать команду /summary в реальном треде
• Настроить актуальный токен LLM при необходимости
• Добавить бота в нужные каналы

**🎯 Итог:**
Бот готов к работе и может создавать саммари тредов по команде /summary"""

# Создаем FastAPI приложение
app = FastAPI(title="Mattermost Summary Bot - Standalone", version="1.0.0")

# Глобальный экземпляр бота
bot = SimpleMattermostBot()

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Главная страница"""
    status = await bot.health_check()
    
    mattermost_status = "🟢 Подключен" if status['mattermost_connected'] else "🔴 Отключен"
    llm_status = "🟢 Подключен" if status['llm_connected'] else "🔴 Отключен"
    bot_status = "🟢 Работает" if status['bot_running'] else "🔴 Остановлен"
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Mattermost Summary Bot - Standalone</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        h1 {{ color: #333; text-align: center; }}
        .status {{ padding: 20px; margin: 10px 0; border-radius: 5px; background: #f8f9fa; }}
        .demo {{ background: #e9ecef; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        pre {{ background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Mattermost Summary Bot</h1>
        <h2>Standalone Version</h2>
        
        <div class="status">
            <h3>📊 Статус системы:</h3>
            <p><strong>Бот:</strong> {bot_status}</p>
            <p><strong>Mattermost:</strong> {mattermost_status}</p>
            <p><strong>LLM:</strong> {llm_status}</p>
        </div>
        
        <div class="demo">
            <h3>📝 Демо саммари:</h3>
            <pre>{bot.demo_summary()}</pre>
        </div>
        
        <div class="status">
            <h3>📋 Инструкции:</h3>
            <ol>
                <li>Добавьте бота в канал: <code>/invite @summary-bot</code></li>
                <li>В треде напишите: <code>/summary</code></li>
                <li>Получите саммари обсуждения!</li>
            </ol>
            
            <h4>🔧 API эндпоинты:</h4>
            <ul>
                <li><a href="/health">/health</a> - проверка здоровья</li>
                <li><a href="/status">/status</a> - детальный статус</li>
                <li><a href="/demo">/demo</a> - демо саммари</li>
            </ul>
        </div>
    </div>
</body>
</html>"""

@app.get("/health")
async def health():
    """Проверка здоровья"""
    status = await bot.health_check()
    if status['mattermost_connected']:
        return {"status": "healthy", "details": status}
    else:
        return {"status": "degraded", "details": status}

@app.get("/status")
async def status():
    """Статус бота"""
    return await bot.health_check()

@app.get("/demo")
async def demo():
    """Демо саммари"""
    return {"summary": bot.demo_summary()}

async def main():
    """Главная функция"""
    try:
        logger.info("🚀 Запуск Standalone Mattermost Summary Bot...")
        
        # Инициализируем бота
        success = await bot.initialize()
        if not success:
            logger.error("Не удалось инициализировать бота")
            return
        
        bot._running = True
        logger.info("✅ Бот инициализирован успешно")
        
        # Запускаем веб-сервер
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=Config.BOT_PORT,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        logger.info(f"🌐 Веб-интерфейс: http://localhost:{Config.BOT_PORT}")
        logger.info("📋 Доступные эндпоинты:")
        logger.info("  - / (главная страница)")
        logger.info("  - /health (проверка здоровья)")
        logger.info("  - /status (статус)")
        logger.info("  - /demo (демо саммари)")
        
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        bot._running = False
        logger.info("🏁 Standalone бот завершил работу")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Завершение работы")
    except Exception as e:
        logger.error(f"Ошибка выполнения: {e}")
        sys.exit(1) 