import asyncio
import logging
import requests
import json
import re
from typing import List, Dict, Any
from config import Config

logger = logging.getLogger(__name__)

class LLMClient:
    """Клиент для работы с корпоративной LLM"""
    
    def __init__(self):
        self.base_url = Config.LLM_BASE_URL.rstrip('/')
        self.model = Config.LLM_MODEL
        self.headers = {
            'X-PROXY-AUTH': Config.LLM_PROXY_TOKEN,  # Правильный заголовок авторизации
            'Content-Type': 'application/json'
        }
    
    async def generate_thread_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Генерирует саммари треда на основе сообщений
        
        Args:
            messages: Список сообщений треда с полями username, message, create_at
            
        Returns:
            Краткое саммари треда
        """
        try:
            # Формируем контекст для LLM
            thread_context = self._format_thread_for_llm(messages)
            
            system_prompt = """Ты - помощник для создания кратких саммари обсуждений в корпоративном мессенджере.

Твоя задача: проанализировать переписку и создать структурированное краткое саммари.

Формат ответа должен быть следующим:
## 📝 Саммари треда

**👥 Участники обсуждения:**
[список участников]

**💬 Основные темы обсуждения:**
[краткое описание основных тем]

**📋 Ключевые моменты:**
[список важных выводов, решений или фактов]

**✅ Задачи и действия:**
[список конкретных задач, действий или договоренностей, если есть]

**🎯 Итог:**
[краткий общий вывод]

Пиши кратко, по существу, на русском языке."""

            # Создаем запрос в формате корпоративной LLM
            payload = {
                "model": self.model,
                "stream": False,
                "messages": [
                    {
                        "role": "system",
                        "content": "/no_think"
                    },
                    {
                        "role": "system", 
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Проанализируй следующую переписку и создай саммари:\n\n{thread_context}"
                    }
                ],
                "options": {
                    "num_ctx": 16384  # 16K токенов контекста
                }
            }

            response = await self._send_request(payload)
            if response:
                return response
            else:
                return "❌ Не удалось создать саммари. Попробуйте позже."
            
        except Exception as e:
            logger.error(f"Ошибка при генерации саммари: {e}")
            return "❌ Не удалось создать саммари. Попробуйте позже."
    
    def _clean_response(self, content: str) -> str:
        """Очищает ответ от thinking-блоков и лишнего форматирования"""
        if not content:
            return content
        
        # Удаляем thinking-блоки
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # Удаляем лишние пустые строки
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # Убираем пробелы в начале и конце
        content = content.strip()
        
        return content
    
    async def _send_request(self, payload: dict) -> str:
        """Отправляет запрос к корпоративной LLM"""
        try:
            url = f"{self.base_url}/api/chat"
            
            logger.info(f"📡 Отправляю запрос к LLM: {url}")
            logger.info(f"🤖 Модель: {self.model}")
            
            # Используем requests с синхронным вызовом в async контексте
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=120  # 2 минуты timeout
                )
            )
            
            if response.status_code == 200:
                response_data = response.json()
                content = response_data.get('message', {}).get('content', '')
                
                if content:
                    # Очищаем ответ от thinking-блоков
                    cleaned_content = self._clean_response(content)
                    logger.info(f"✅ Получен ответ от LLM ({len(content)} символов, после очистки: {len(cleaned_content)} символов)")
                    return cleaned_content
                else:
                    logger.warning("⚠️ Получен пустой ответ от LLM")
                    return ""
            else:
                logger.error(f"❌ Ошибка HTTP {response.status_code}: {response.text}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Ошибка при запросе к LLM: {str(e)}")
            return ""
    
    def _format_thread_for_llm(self, messages: List[Dict[str, Any]]) -> str:
        """Форматирует сообщения треда для передачи в LLM"""
        formatted_messages = []
        
        for msg in messages:
            username = msg.get('username', 'Неизвестный пользователь')
            message = msg.get('message', '')
            timestamp = msg.get('create_at', '')
            
            # Убираем лишние символы и форматируем
            clean_message = message.strip()
            if clean_message:
                formatted_messages.append(f"{username}: {clean_message}")
        
        return "\n".join(formatted_messages)
    
    async def test_connection(self) -> bool:
        """Тестирует соединение с LLM"""
        try:
            payload = {
                "model": self.model,
                "stream": False,
                "messages": [
                    {
                        "role": "system",
                        "content": "/no_think"
                    },
                    {
                        "role": "user",
                        "content": "Тест соединения"
                    }
                ],
                "options": {
                    "num_ctx": 4096
                }
            }
            
            url = f"{self.base_url}/api/chat"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
            )
            
            if response.status_code == 200:
                logger.info("✅ LLM соединение успешно")
                return True
            else:
                logger.error(f"❌ LLM соединение неуспешно: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка соединения с LLM: {e}")
            return False 