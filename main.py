#!/usr/bin/env python3
"""
Главная точка входа для Mattermost Summary Bot
"""

import asyncio
import logging
import signal
import sys

from config import Config
from mattermost_bot import MattermostBot
from web_server import create_app
import uvicorn

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class BotApplication:
    """Основное приложение, объединяющее бота и веб-сервер"""
    
    def __init__(self):
        self.bot = MattermostBot()
        self.web_app = None
        self.tasks = []
        self._shutdown = False
    
    async def start(self):
        """Запуск приложения"""
        try:
            logger.info("🚀 Запуск Mattermost Summary Bot...")
            
            # Инициализируем бота
            if not await self.bot.initialize():
                logger.error("❌ Не удалось инициализировать бота")
                return False
            
            # Создаем веб-приложение с ботом
            self.web_app = create_app(self.bot)
            
            # Запускаем задачи параллельно
            tasks = [
                asyncio.create_task(self._run_bot(), name="mattermost_bot"),
                asyncio.create_task(self._run_web_server(), name="web_server")
            ]
            
            self.tasks = tasks
            
            # Настройка обработчиков сигналов
            self._setup_signal_handlers()
            
            logger.info("🎉 Все компоненты запущены успешно!")
            logger.info(f"🌐 Веб-интерфейс: http://0.0.0.0:{Config.BOT_PORT}")
            logger.info("📝 Для остановки нажмите Ctrl+C")
            
            # Ожидаем завершения всех задач
            await asyncio.gather(*tasks, return_exceptions=True)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при запуске: {e}")
            return False
    
    async def _run_bot(self):
        """Запуск Mattermost бота"""
        try:
            await self.bot.start_listening()
        except Exception as e:
            logger.error(f"❌ Ошибка в работе бота: {e}")
            await self.shutdown()
    
    async def _run_web_server(self):
        """Запуск веб-сервера"""
        try:
            config = uvicorn.Config(
                self.web_app,
                host="0.0.0.0",
                port=Config.BOT_PORT,
                log_level="warning",  # Снижаем уровень логирования uvicorn
                access_log=False
            )
            server = uvicorn.Server(config)
            await server.serve()
        except Exception as e:
            if not self._shutdown:
                logger.error(f"❌ Ошибка веб-сервера: {e}")
                await self.shutdown()
    
    def _setup_signal_handlers(self):
        """Настройка обработчиков системных сигналов"""
        def signal_handler(sig, frame):
            logger.info(f"📨 Получен сигнал {sig}")
            asyncio.create_task(self.shutdown())
        
        try:
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
        except ValueError:
            # В некоторых средах (например, Windows) SIGTERM может быть недоступен
            signal.signal(signal.SIGINT, signal_handler)
    
    async def shutdown(self):
        """Корректное завершение работы"""
        if self._shutdown:
            return
        
        self._shutdown = True
        logger.info("🛑 Начинаю корректное завершение работы...")
        
        # Останавливаем бота
        try:
            self.bot.stop()
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")
        
        # Отменяем все задачи
        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"❌ Ошибка при отмене задачи {task.get_name()}: {e}")
        
        logger.info("✅ Корректное завершение работы завершено")

async def main():
    """Главная функция"""
    app = BotApplication()
    
    try:
        success = await app.start()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("📝 Получен сигнал прерывания")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)
    finally:
        await app.shutdown()

if __name__ == "__main__":
    try:
        # Проверяем конфигурацию
        Config.validate()
        
        # Запускаем приложение
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("👋 До свидания!")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1) 