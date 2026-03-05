import logging
import re
from typing import List, Dict, Any
from openai import AsyncOpenAI
from config import Config

logger = logging.getLogger(__name__)

class LLMClient:
    """Клиент для работы с корпоративной LLM"""
    
    def __init__(self):
        self.base_url = Config.LLM_BASE_URL.rstrip('/')
        self.model = Config.LLM_MODEL
        self.client = AsyncOpenAI(
            api_key=Config.LLM_PROXY_TOKEN,
            base_url=self.base_url,
        )
    
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

            messages_payload = [
                {"role": "system", "content": "/no_think"},
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Проанализируй следующую переписку и создай саммари:\n\n{thread_context}"
                },
            ]

            response = await self._send_chat_completion(messages_payload)
            if response:
                return response
            else:
                return "❌ Не удалось создать саммари. Попробуйте позже."
            
        except Exception as e:
            logger.error(f"Ошибка при генерации саммари: {e}")
            return "❌ Не удалось создать саммари. Попробуйте позже."
    
    async def generate_channel_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Генерирует саммари канала на основе сообщений за определенный период
        
        Args:
            messages: Список сообщений канала с полями username, message, create_at
            
        Returns:
            Краткое саммари канала
        """
        try:
            # Формируем контекст для LLM
            channel_context = self._format_channel_for_llm(messages)
            
            system_prompt = """Ты - помощник для создания кратких саммари активности в корпоративном канале.

Твоя задача: проанализировать сообщения из канала и создать структурированное краткое саммари.

Формат ответа должен быть следующим:
## 📊 Саммари канала

**👥 Активные участники:**
[список самых активных участников]

**💬 Основные темы обсуждения:**
[краткое описание основных тем и направлений разговора]

**📋 Ключевые моменты:**
[список важных выводов, решений, объявлений или фактов]

**🔗 Важные ссылки и файлы:**
[если есть важные ссылки, файлы или ресурсы]

**✅ Задачи и действия:**
[список конкретных задач, действий или договоренностей, если есть]

**🎯 Общий итог:**
[краткий общий вывод о активности в канале]

Пиши кратко, по существу, на русском языке. Группируй похожие темы."""

            messages_payload = [
                {"role": "system", "content": "/no_think"},
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Проанализируй следующие сообщения из канала и создай саммари:\n\n{channel_context}"
                },
            ]
            
            # Отправляем запрос к LLM
            response = await self._send_chat_completion(messages_payload)
            
            if response:
                return response.strip()
            else:
                return "❌ Не удалось создать саммари канала. Попробуйте позже."
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации саммари канала: {e}")
            return "❌ Не удалось создать саммари канала. Попробуйте позже."
    
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
    
    def _extract_content_from_completion(self, response: Any) -> str:
        """Извлекает текст из ответа chat.completions."""
        choices = getattr(response, "choices", None)
        if not choices:
            return ""

        message = getattr(choices[0], "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", None)
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text" and part.get("text"):
                        text_parts.append(part["text"])
                    continue

                part_type = getattr(part, "type", None)
                part_text = getattr(part, "text", None)
                if part_type == "text" and part_text:
                    text_parts.append(part_text)

            return "".join(text_parts)

        return ""

    async def _send_chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """Отправляет запрос в LiteLLM через OpenAI chat.completions."""
        try:
            logger.info(f"📡 Отправляю запрос к LLM: {self.base_url}")
            logger.info(f"🤖 Модель: {self.model}")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )

            content = self._extract_content_from_completion(response)
            if not content:
                logger.warning("⚠️ Не найден контент в ответе от LLM")
                return ""

            cleaned_content = self._clean_response(content)
            logger.info(
                f"✅ Получен ответ от LLM ({len(content)} символов, после очистки: {len(cleaned_content)} символов)"
            )
            return cleaned_content

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
    
    def _format_channel_for_llm(self, messages: List[Dict[str, Any]]) -> str:
        """Форматирует сообщения канала для передачи в LLM"""
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
    
    async def generate_channels_summary(self, messages: List[Dict[str, Any]], 
                                       channel_summaries: List[Dict], frequency: str) -> str:
        """
        Генерирует сводку по нескольким каналам
        
        Args:
            messages: Список всех сообщений из каналов
            channel_summaries: Информация о каналах
            frequency: Частота отправки (daily/weekly)
            
        Returns:
            Сводка по каналам
        """
        try:
            # Формируем контекст для LLM
            channels_context = self._format_channels_for_llm(messages, channel_summaries)
            
            period = "за последние 24 часа" if frequency == 'daily' else "за последнюю неделю"
            
            system_prompt = f"""Ты - помощник для создания сводок активности в корпоративных каналах.

Твоя задача: проанализировать сообщения из нескольких каналов {period} и создать структурированную сводку.

Формат ответа должен быть следующим:
## 📊 Сводка активности каналов

**🔥 Самые активные обсуждения:**
[перечисли наиболее активные темы и их каналы]

**👥 Активные участники:**
[перечисли самых активных участников]

**📋 Ключевые темы и решения:**
[список важных вопросов, решений или объявлений по каналам]

**🔗 Интересные ссылки и файлы:**
[если есть важные ссылки или файлы]

**💡 Краткие выводы:**
[общие выводы о активности и тенденциях]

Будь кратким, но информативным. Группируй похожие темы. Указывай канал для важных обсуждений.
"""
            
            user_prompt = f"""Проанализируй активность в каналах {period} и создай сводку:

{channels_context}

Создай краткую, но информативную сводку активности."""
            
            messages_payload = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = await self._send_chat_completion(messages_payload)
            
            if response:
                return response
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка генерации сводки каналов: {e}")
            return None
    
    def _format_channels_for_llm(self, messages: List[Dict[str, Any]], 
                                channel_summaries: List[Dict]) -> str:
        """Форматирует сообщения из каналов для передачи в LLM"""
        # Группируем сообщения по каналам
        channels_data = {}
        for channel_info in channel_summaries:
            channel_name = channel_info['channel_name']
            channels_data[channel_name] = {
                'display_name': channel_info['display_name'],
                'messages': []
            }
        
        # Сортируем сообщения по каналам
        for msg in messages:
            channel_name = msg.get('channel_name', 'unknown')
            if channel_name in channels_data:
                channels_data[channel_name]['messages'].append(msg)
        
        # Форматируем для LLM
        formatted_channels = []
        
        for channel_name, data in channels_data.items():
            if data['messages']:
                formatted_channels.append(f"\n=== КАНАЛ: {data['display_name']} ===")
                
                # Сортируем сообщения по времени
                sorted_messages = sorted(data['messages'], key=lambda x: x.get('create_at', 0))
                
                for msg in sorted_messages:
                    username = msg.get('username', 'Неизвестный пользователь')
                    message = msg.get('message', '')
                    
                    # Убираем лишние символы
                    clean_message = message.strip()
                    if clean_message:
                        formatted_channels.append(f"{username}: {clean_message}")
                
                formatted_channels.append("")  # Пустая строка между каналами
        
        return "\n".join(formatted_channels)
    
    async def test_connection(self) -> bool:
        """Тестирует соединение с LLM"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "/no_think"},
                    {"role": "user", "content": "Тест соединения"},
                ],
            )
            if response:
                logger.info("✅ LLM соединение успешно")
                return True
            logger.error("❌ LLM соединение неуспешно: пустой ответ")
            return False
                
        except Exception as e:
            logger.error(f"Ошибка соединения с LLM: {e}")
            return False 