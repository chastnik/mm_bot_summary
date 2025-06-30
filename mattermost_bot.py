#!/usr/bin/env python3
"""
Mattermost Summary Bot
Основанный на лучших практиках из reference проектов
"""

import asyncio
import json
import logging
import re
import requests
import websockets
import ssl
import time
from typing import Dict, List, Any, Optional, Callable
from urllib.parse import urlparse, parse_qs

from config import Config
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class MattermostBot:
    """
    Основной класс бота для Mattermost
    Использует WebSocket для получения событий в реальном времени
    """
    
    def __init__(self):
        self.base_url = None
        self.token = None
        self.bot_user_id = None
        self.bot_username = None
        self.llm_client = LLMClient()
        self._running = False
        self._websocket = None
        self._session_requests = requests.Session()
        self._message_handlers = []
        
    async def initialize(self):
        """Инициализация бота"""
        try:
            logger.info("🤖 Инициализация Mattermost Summary Bot...")
            
            # Проверяем конфигурацию
            Config.validate()
            
            # Подготавливаем URL
            self.base_url = Config.MATTERMOST_URL.strip().rstrip('/')
            if not self.base_url.startswith(('http://', 'https://')):
                self.base_url = 'https://' + self.base_url
            
            self.token = Config.MATTERMOST_TOKEN
            
            # Настраиваем сессию для HTTP запросов
            self._session_requests.headers.update({
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            })
            
            # Проверяем подключение к Mattermost
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/users/me", 
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Ошибка аутентификации в Mattermost: {response.status_code}")
                return False
            
            user_data = response.json()
            self.bot_user_id = user_data['id']
            self.bot_username = user_data['username']
            
            logger.info(f"✅ Подключен к Mattermost как {self.bot_username} (ID: {self.bot_user_id})")
            
            # Тестируем соединение с LLM
            llm_ok = await self.llm_client.test_connection()
            if llm_ok:
                logger.info("✅ Соединение с LLM установлено")
            else:
                logger.warning("⚠️ Проблемы с соединением с LLM")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}")
            return False
    
    async def start_listening(self):
        """Запуск прослушивания событий через WebSocket"""
        if not self.base_url or not self.token:
            logger.error("❌ Бот не инициализирован")
            return
        
        self._running = True
        logger.info("🎧 Начинаю прослушивание событий WebSocket...")
        
        # Основной цикл переподключения
        while self._running:
            try:
                await self._connect_websocket()
            except Exception as e:
                logger.error(f"❌ Ошибка WebSocket соединения: {e}")
                if self._running:
                    logger.info("🔄 Переподключение через 5 секунд...")
                    await asyncio.sleep(5)
    
    async def _connect_websocket(self):
        """Подключение к WebSocket"""
        # Парсим URL для WebSocket
        parsed_url = urlparse(self.base_url)
        
        # Определяем схему WebSocket
        ws_scheme = 'wss' if parsed_url.scheme == 'https' else 'ws'
        ws_port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
        
        ws_url = f"{ws_scheme}://{parsed_url.hostname}:{ws_port}/api/v4/websocket"
        
        logger.info(f"🔌 Подключение к WebSocket: {ws_url}")
        
        # Настройка SSL контекста
        ssl_context = None
        if ws_scheme == 'wss':
            ssl_context = ssl.create_default_context()
            # Для разработки можно отключить проверку сертификатов
            # ssl_context.check_hostname = False
            # ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            # Подключение к WebSocket
            async with websockets.connect(
                ws_url,
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                self._websocket = websocket
                
                # Аутентификация
                await self._authenticate_websocket()
                
                logger.info("✅ WebSocket подключен и аутентифицирован")
                
                # Основной цикл обработки сообщений
                async for message in websocket:
                    if not self._running:
                        break
                    await self._handle_websocket_message(message)
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket соединение закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка WebSocket: {e}")
            raise
    
    async def _authenticate_websocket(self):
        """Аутентификация WebSocket соединения"""
        auth_message = {
            "seq": 1,
            "action": "authentication_challenge",
            "data": {
                "token": self.token
            }
        }
        
        await self._websocket.send(json.dumps(auth_message))
        
        # Ждем подтверждения аутентификации
        auth_timeout = 10
        start_time = time.time()
        
        while time.time() - start_time < auth_timeout:
            try:
                message = await asyncio.wait_for(self._websocket.recv(), timeout=1.0)
                event = json.loads(message)
                
                if event.get('event') == 'hello':
                    logger.info("✅ WebSocket аутентификация успешна")
                    return
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ Ошибка аутентификации WebSocket: {e}")
                raise
        
        raise Exception("Таймаут аутентификации WebSocket")
    
    async def _handle_websocket_message(self, message: str):
        """Обработка сообщения от WebSocket"""
        try:
            event = json.loads(message)
            
            # Обрабатываем события постов
            if event.get('event') == 'posted':
                await self._handle_post_event(event)
            elif event.get('event') == 'hello':
                logger.debug("💬 Получен hello от WebSocket")
            else:
                logger.debug(f"💬 Событие WebSocket: {event.get('event')}")
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON от WebSocket: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка обработки WebSocket сообщения: {e}")
    
    async def _handle_post_event(self, event: Dict[str, Any]):
        """Обработка события нового поста"""
        try:
            # Извлекаем данные поста
            post_data = event.get('data', {}).get('post')
            if not post_data:
                return
            
            # Парсим пост (может быть строкой JSON)
            if isinstance(post_data, str):
                post = json.loads(post_data)
            else:
                post = post_data
            
            # Игнорируем сообщения от самого бота
            if post.get('user_id') == self.bot_user_id:
                return
            
            message = post.get('message', '').strip()
            channel_id = post.get('channel_id')
            post_id = post.get('id')
            root_id = post.get('root_id') or post_id  # ID треда или самого поста
            
            # Логируем только команды
            if self._is_summary_command(message):
                logger.info(f"📝 Получена команда /summary в канале {channel_id}")
                await self._handle_summary_command(channel_id, root_id, post_id)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки события поста: {e}")
    
    def _is_summary_command(self, message: str) -> bool:
        """Проверяет, является ли сообщение командой /summary"""
        patterns = [
            r'^/summary\s*$',
            r'^!summary\s*$', 
            r'^summary\s*$',
            r'^саммари\s*$',
            r'^/саммари\s*$'
        ]
        
        message_lower = message.lower()
        return any(re.match(pattern, message_lower) for pattern in patterns)
    
    async def _handle_summary_command(self, channel_id: str, thread_id: str, message_id: str):
        """Обработка команды создания саммари"""
        try:
            # Отправляем уведомление о начале обработки
            await self._send_message(
                channel_id, 
                "🔄 Создаю саммари треда... Это может занять несколько секунд.",
                root_id=thread_id
            )
            
            # Получаем все сообщения треда
            thread_messages = await self._get_thread_messages(thread_id)
            
            if not thread_messages:
                await self._send_message(
                    channel_id,
                    "❌ Не удалось получить сообщения треда или тред пустой.",
                    root_id=thread_id
                )
                return
            
            logger.info(f"📊 Обрабатываю {len(thread_messages)} сообщений в треде")
            
            # Генерируем саммари
            summary = await self.llm_client.generate_thread_summary(thread_messages)
            
            # Отправляем саммари
            await self._send_message(channel_id, summary, root_id=thread_id)
            logger.info("✅ Саммари отправлено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при создании саммари: {e}")
            await self._send_message(
                channel_id,
                "❌ Произошла ошибка при создании саммари. Попробуйте позже.",
                root_id=thread_id
            )
    
    async def _get_thread_messages(self, thread_id: str) -> List[Dict[str, Any]]:
        """Получает все сообщения треда"""
        try:
            # Получаем пост-родитель и все ответы
            root_response = self._session_requests.get(
                f"{self.base_url}/api/v4/posts/{thread_id}",
                timeout=10
            )
            
            if root_response.status_code != 200:
                logger.error(f"❌ Ошибка получения корневого поста: {root_response.status_code}")
                return []
            
            # Получаем тред
            thread_response = self._session_requests.get(
                f"{self.base_url}/api/v4/posts/{thread_id}/thread",
                timeout=10
            )
            
            if thread_response.status_code != 200:
                logger.error(f"❌ Ошибка получения треда: {thread_response.status_code}")
                return []
            
            root_post = root_response.json()
            thread_data = thread_response.json()
            
            messages = []
            all_posts = [root_post]
            
            # Добавляем все посты из треда
            posts_dict = thread_data.get('posts', {})
            order = thread_data.get('order', [])
            
            # Сортируем посты по порядку
            for post_id in order:
                if post_id in posts_dict and post_id != thread_id:
                    all_posts.append(posts_dict[post_id])
            
            # Сортируем по времени создания для надежности
            all_posts.sort(key=lambda x: x.get('create_at', 0))
            
            # Кешируем пользователей
            user_cache = {}
            
            for post in all_posts:
                user_id = post.get('user_id')
                
                # Получаем имя пользователя (с кешированием)
                if user_id not in user_cache:
                    try:
                        user_response = self._session_requests.get(
                            f"{self.base_url}/api/v4/users/{user_id}",
                            timeout=5
                        )
                        if user_response.status_code == 200:
                            user_data = user_response.json()
                            user_cache[user_id] = user_data.get('username', 'Неизвестный')
                        else:
                            user_cache[user_id] = 'Неизвестный'
                    except:
                        user_cache[user_id] = 'Неизвестный'
                
                username = user_cache[user_id]
                
                messages.append({
                    'username': username,
                    'message': post.get('message', ''),
                    'create_at': post.get('create_at', 0),
                    'user_id': user_id
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сообщений треда: {e}")
            return []
    
    async def _send_message(self, channel_id: str, message: str, root_id: Optional[str] = None):
        """Отправляет сообщение в канал"""
        try:
            post_data = {
                'channel_id': channel_id,
                'message': message
            }
            
            if root_id:
                post_data['root_id'] = root_id
            
            response = self._session_requests.post(
                f"{self.base_url}/api/v4/posts",
                json=post_data,
                timeout=10
            )
            
            if response.status_code == 201:
                logger.debug("📤 Сообщение отправлено успешно")
            else:
                logger.error(f"❌ Ошибка отправки сообщения: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
    
    def stop(self):
        """Остановка бота"""
        logger.info("🛑 Остановка бота...")
        self._running = False
        
        if self._websocket:
            try:
                asyncio.create_task(self._websocket.close())
            except:
                pass
        
        logger.info("✅ Бот остановлен")
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка состояния бота"""
        status = {
            'mattermost_connected': False,
            'llm_connected': False,
            'bot_running': self._running,
            'websocket_connected': self._websocket is not None and hasattr(self._websocket, 'closed') and not self._websocket.closed,
            'bot_username': self.bot_username,
            'bot_user_id': self.bot_user_id
        }
        
        # Проверяем соединение с Mattermost
        try:
            if self.base_url and self.token:
                response = self._session_requests.get(
                    f"{self.base_url}/api/v4/users/me",
                    timeout=5
                )
                status['mattermost_connected'] = response.status_code == 200
        except:
            status['mattermost_connected'] = False
        
        # Проверяем соединение с LLM
        try:
            status['llm_connected'] = await self.llm_client.test_connection()
        except:
            status['llm_connected'] = False
        
        return status 