import asyncio
import logging
from typing import List, Dict, Any
from openai import AsyncOpenAI
from config import Config

logger = logging.getLogger(__name__)

class LLMClient:
    """Клиент для работы с корпоративной LLM"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=Config.LLM_PROXY_TOKEN,
            base_url=Config.LLM_BASE_URL
        )
        self.model = Config.LLM_MODEL
    
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

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Проанализируй следующую переписку и создай саммари:\n\n{thread_context}"}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации саммари: {e}")
            return "❌ Не удалось создать саммари. Попробуйте позже."
    
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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Тест соединения"}],
                max_tokens=10
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка соединения с LLM: {e}")
            return False 