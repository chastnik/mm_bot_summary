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
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

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
            
            # Получаем список каналов, в которых уже находится бот
            await self._load_existing_channels()
            
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
    
    async def _load_existing_channels(self):
        """Загружает список каналов, в которых уже находится бот"""
        try:
            # Получаем список каналов для текущего пользователя (бота)
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/users/me/channels",
                timeout=10
            )
            
            if response.status_code == 200:
                channels = response.json()
                channel_count = len(channels)
                
                logger.info(f"📋 Бот уже находится в {channel_count} канал(ах)")
                
                # Логируем типы каналов
                types_count = {}
                for channel in channels:
                    channel_type = channel.get('type', 'unknown')
                    types_count[channel_type] = types_count.get(channel_type, 0) + 1
                
                type_names = {
                    'O': 'открытых',
                    'P': 'приватных', 
                    'D': 'личных сообщений',
                    'G': 'групповых'
                }
                
                for type_code, count in types_count.items():
                    type_name = type_names.get(type_code, f'типа {type_code}')
                    logger.info(f"   • {count} {type_name} каналов")
                    
            else:
                logger.warning(f"⚠️ Не удалось получить список каналов: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки списка каналов: {e}")
    
    async def _check_channel_permissions(self, channel_id: str) -> bool:
        """Проверяет разрешения бота в канале"""
        try:
            # Проверяем, есть ли доступ к каналу
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/channels/{channel_id}/members/me",
                timeout=5
            )
            
            if response.status_code == 200:
                member_info = response.json()
                return True
            else:
                logger.warning(f"⚠️ Нет доступа к каналу {channel_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки разрешений в канале {channel_id}: {e}")
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
                    # Обрабатываем разные типы сообщений WebSocket
                    if isinstance(message, bytes):
                        message_str = message.decode()
                    else:
                        message_str = str(message)
                    await self._handle_websocket_message(message_str)
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket соединение закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка WebSocket: {e}")
            raise
    
    async def _authenticate_websocket(self):
        """Аутентификация WebSocket соединения"""
        if self._websocket is None:
            raise Exception("WebSocket соединение не установлено")
            
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
            event_type = event.get('event')
            
            # Обрабатываем различные типы событий
            if event_type == 'posted':
                await self._handle_post_event(event)
            elif event_type == 'user_added':
                await self._handle_user_added_event(event)
            elif event_type == 'channel_member_added':
                await self._handle_channel_member_added_event(event)
            elif event_type == 'hello':
                logger.debug("💬 Получен hello от WebSocket")
            else:
                logger.debug(f"💬 Событие WebSocket: {event_type}")
                
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
    
    async def _handle_user_added_event(self, event: Dict[str, Any]):
        """Обработка события добавления пользователя в канал"""
        try:
            data = event.get('data', {})
            user_id = data.get('user_id')
            channel_id = data.get('channel_id')
            
            # Проверяем, не добавили ли нашего бота в канал
            if user_id == self.bot_user_id:
                logger.info(f"🎉 Бот добавлен в новый канал: {channel_id}")
                await self._initialize_in_channel(channel_id)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки события user_added: {e}")
    
    async def _handle_channel_member_added_event(self, event: Dict[str, Any]):
        """Обработка события добавления участника в канал"""
        try:
            data = event.get('data', {})
            user_id = data.get('user_id')
            channel_id = data.get('channel_id')
            
            # Проверяем, не добавили ли нашего бота в канал
            if user_id == self.bot_user_id:
                logger.info(f"🎉 Бот добавлен в канал: {channel_id}")
                await self._initialize_in_channel(channel_id)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки события channel_member_added: {e}")
    
    async def _initialize_in_channel(self, channel_id: str):
        """Инициализация бота в новом канале"""
        try:
            # Получаем информацию о канале
            channel_info = await self._get_channel_info(channel_id)
            if not channel_info:
                return
            
            channel_name = channel_info.get('display_name', channel_info.get('name', 'неизвестный'))
            channel_type = channel_info.get('type', 'O')  # O=open, P=private, D=direct
            
            # Определяем тип канала для логирования
            type_emoji = {
                'O': '🌐',  # Открытый канал
                'P': '🔒',  # Приватный канал  
                'D': '💬'   # Прямые сообщения
            }.get(channel_type, '📁')
            
            logger.info(f"{type_emoji} Инициализация в канале '{channel_name}' (ID: {channel_id})")
            
            # Отправляем приветственное сообщение (только для открытых и приватных каналов)
            if channel_type in ['O', 'P']:
                welcome_message = f"""👋 Привет! Я **Summary Bot** - помогаю создавать саммари тредов.

**Как использовать:**
• В любом треде напишите `!summary` - создам краткое резюме обсуждения
• Поддерживаю команды: `!summary`, `summary`, `саммари`, `!саммари`

**⚠️ Важно:** Команды с `/` (например `/summary`) в Mattermost зарезервированы для системных слэш-команд. Используйте команды с `!` или без символов.

**Что я анализирую:**
• Участников обсуждения
• Основные темы и моменты
• Задачи и выводы
• Структурированное резюме

Готов к работе! 🚀"""
                
                await self._send_message(channel_id, welcome_message)
                logger.info(f"✅ Приветственное сообщение отправлено в {channel_name}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации в канале {channel_id}: {e}")
    
    async def _get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о канале"""
        try:
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/channels/{channel_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Ошибка получения информации о канале {channel_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка запроса информации о канале {channel_id}: {e}")
            return None
    
    def _is_summary_command(self, message: str) -> bool:
        """Проверяет, является ли сообщение командой summary"""
        patterns = [
            r'^!summary\s*$',      # !summary - работает как обычное сообщение
            r'^summary\s*$',       # summary - простая команда
            r'^саммари\s*$',       # саммари - русская команда
            r'^!саммари\s*$'       # !саммари - русская с восклицательным знаком
        ]
        
        message_lower = message.lower()
        return any(re.match(pattern, message_lower) for pattern in patterns)
    
    async def _handle_summary_command(self, channel_id: str, thread_id: str, message_id: str):
        """Обработка команды создания саммари"""
        try:
            # Проверяем разрешения в канале
            if not await self._check_channel_permissions(channel_id):
                logger.warning(f"⚠️ Нет разрешений для ответа в канале {channel_id}")
                return
            
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
            
            # Проверяем минимальное количество сообщений для саммари
            if len(thread_messages) < 2:
                await self._send_message(
                    channel_id,
                    "📝 В треде недостаточно сообщений для создания саммари (минимум 2 сообщения).",
                    root_id=thread_id
                )
                return
            
            logger.info(f"📊 Обрабатываю {len(thread_messages)} сообщений в треде")
            
            # Генерируем саммари
            summary = await self.llm_client.generate_thread_summary(thread_messages)
            
            if summary:
                # Отправляем саммари
                await self._send_message(channel_id, summary, root_id=thread_id)
                logger.info("✅ Саммари отправлено")
            else:
                await self._send_message(
                    channel_id,
                    "❌ Не удалось сгенерировать саммари. Возможно, проблемы с LLM сервисом.",
                    root_id=thread_id
                )
            
        except Exception as e:
            logger.error(f"❌ Ошибка при создании саммари: {e}")
            try:
                await self._send_message(
                    channel_id,
                    "❌ Произошла ошибка при создании саммари. Попробуйте позже.",
                    root_id=thread_id
                )
            except:
                # Если даже отправка сообщения об ошибке не удалась
                logger.error("❌ Критическая ошибка: не удалось отправить сообщение об ошибке")
    
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
        # Безопасная проверка WebSocket соединения
        websocket_connected = False
        if self._websocket is not None:
            try:
                # Проверяем, что соединение открыто
                websocket_connected = not getattr(self._websocket, 'closed', True)
            except:
                websocket_connected = False
        
        status = {
            'mattermost_connected': False,
            'llm_connected': False,
            'bot_running': self._running,
            'websocket_connected': websocket_connected,
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