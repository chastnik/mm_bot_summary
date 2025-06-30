import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация бота"""
    
    # Mattermost настройки
    MATTERMOST_URL = os.getenv('MATTERMOST_URL', '')
    MATTERMOST_TOKEN = os.getenv('MATTERMOST_TOKEN', '')
    MATTERMOST_BOT_USERNAME = os.getenv('MATTERMOST_BOT_USERNAME', 'summary-bot')
    
    # LLM настройки
    LLM_PROXY_TOKEN = os.getenv('LLM_PROXY_TOKEN', '8d10b6d4-2e40-42fc-a66a-c9c6bf20c92c')
    LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://llm.1bitai.ru')
    LLM_MODEL = os.getenv('LLM_MODEL', 'qwen3:14b')
    
    # Общие настройки бота
    BOT_PORT = int(os.getenv('BOT_PORT', 8080))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    
    @classmethod
    def validate(cls):
        """Проверка обязательных настроек"""
        if not cls.MATTERMOST_URL or cls.MATTERMOST_URL == 'https://your-mattermost-instance.com':
            raise ValueError("MATTERMOST_URL не задан или содержит примерное значение. Укажите реальный URL вашего Mattermost сервера.")
        if not cls.MATTERMOST_TOKEN or cls.MATTERMOST_TOKEN == 'your-bot-token':
            raise ValueError("MATTERMOST_TOKEN не задан или содержит примерное значение. Создайте бота в Mattermost и укажите его токен.")
        return True 