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
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from config import Config
from llm_client import LLMClient
from subscription_manager import SubscriptionManager

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
        self.subscription_manager = SubscriptionManager()
        self._running = False
        self._websocket = None
        self._session_requests = requests.Session()
        
        # Состояния пользователей для обработки команд
        self._user_states = {}
        
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
            # Способ 1: Проверяем членство через API
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/channels/{channel_id}/members/me",
                timeout=5
            )
            
            if response.status_code == 200:
                member_info = response.json()
                logger.info(f"✅ Подтверждено членство в канале {channel_id}")
                return True
            
            # Способ 2: Если первый способ не сработал, проверяем через список каналов
            logger.info(f"🔍 Первичная проверка не прошла ({response.status_code}), проверяем через список каналов...")
            
            channels_response = self._session_requests.get(
                f"{self.base_url}/api/v4/users/me/channels",
                timeout=10
            )
            
            if channels_response.status_code == 200:
                all_channels = channels_response.json()
                
                # Проверяем, есть ли канал в списке каналов бота
                for channel in all_channels:
                    if channel.get('id') == channel_id:
                        logger.info(f"✅ Канал {channel_id} найден в списке каналов бота")
                        return True
                
                logger.warning(f"⚠️ Канал {channel_id} не найден в списке каналов бота")
            
            # Способ 3: Попытка получить базовую информацию о канале
            logger.info(f"🔍 Проверяем базовый доступ к информации о канале {channel_id}...")
            
            channel_info_response = self._session_requests.get(
                f"{self.base_url}/api/v4/channels/{channel_id}",
                timeout=5
            )
            
            if channel_info_response.status_code == 200:
                logger.info(f"✅ Базовая информация о канале {channel_id} доступна")
                return True
            else:
                logger.warning(f"⚠️ Базовая информация о канале {channel_id} недоступна: {channel_info_response.status_code}")
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
            user_id = post.get('user_id')
            root_id = post.get('root_id') or post_id  # ID треда или самого поста
            
            # Проверяем, является ли это личным сообщением
            if self._is_direct_message(channel_id):
                await self._handle_direct_message(channel_id, message, user_id)
                return
            
            # Логируем только команды саммари в каналах
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
• В любом треде используйте команду для создания саммари: `!summary`, `summary`, `саммари`, `!саммари`

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
    
    async def get_channel_by_name(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """Получение информации о канале по имени, отображаемому имени или ID"""
        try:
            # Убираем ~ в начале если есть
            clean_channel_name = channel_name.lstrip('~')
            
            # Проверяем, похоже ли это на ID канала (длинная строка из букв и цифр)
            if len(clean_channel_name) >= 20 and clean_channel_name.isalnum():
                logger.info(f"🔍 Поиск канала по ID: {clean_channel_name}")
                
                # Пытаемся найти по ID
                id_response = self._session_requests.get(
                    f"{self.base_url}/api/v4/channels/{clean_channel_name}",
                    timeout=10
                )
                
                if id_response.status_code == 200:
                    channel_data = id_response.json()
                    logger.info(f"✅ Найден канал по ID: '{channel_data.get('display_name', channel_data.get('name', 'неизвестный'))}' (ID: {clean_channel_name})")
                    return channel_data
                else:
                    logger.info(f"⚠️ Канал с ID {clean_channel_name} не найден или нет доступа ({id_response.status_code})")
            
            # Сначала пытаемся найти по внутреннему имени (без пробелов)
            # Преобразуем в формат, подходящий для внутреннего имени
            internal_name = clean_channel_name.lower().replace(' ', '-').replace('_', '-')
            
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/channels/name/{internal_name}",
                timeout=10
            )
            
            if response.status_code == 200:
                channel_data = response.json()
                logger.info(f"✅ Найден канал по внутреннему имени: '{channel_data.get('display_name', channel_data.get('name', 'неизвестный'))}' (внутреннее имя: {internal_name})")
                return channel_data
            
            # Если не найден по внутреннему имени, ищем по display_name среди всех каналов
            logger.info(f"🔍 Поиск канала '{clean_channel_name}' по display_name...")
            
            # Получаем все каналы, в которых участвует бот
            channels_response = self._session_requests.get(
                f"{self.base_url}/api/v4/users/me/channels",
                timeout=10
            )
            
            if channels_response.status_code == 200:
                all_channels = channels_response.json()
                
                # Ищем канал по display_name или name
                for channel in all_channels:
                    channel_display_name = channel.get('display_name', '')
                    channel_internal_name = channel.get('name', '')
                    
                    # Сравниваем с оригинальным именем
                    if (clean_channel_name.lower() == channel_display_name.lower() or
                        clean_channel_name.lower() == channel_internal_name.lower() or
                        internal_name == channel_internal_name):
                        logger.info(f"✅ Найден канал '{channel_display_name}' (внутреннее имя: {channel_internal_name})")
                        return channel
                
            logger.warning(f"⚠️ Канал '{channel_name}' не найден ни по ID, ни по внутреннему имени, ни по отображаемому имени")
            return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения канала {channel_name}: {e}")
            return None
    
    async def get_channel_messages_since(self, channel_id: str, since_time: datetime) -> List[Dict[str, Any]]:
        """Получение сообщений из канала с определенного времени"""
        try:
            # Конвертируем время в миллисекунды (формат Mattermost)
            since_timestamp = int(since_time.timestamp() * 1000)
            
            # Получаем сообщения из канала
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/channels/{channel_id}/posts",
                params={
                    'since': since_timestamp,
                    'per_page': 200  # Максимум сообщений
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Ошибка получения сообщений канала {channel_id}: {response.status_code}")
                return []
            
            posts_data = response.json()
            posts = posts_data.get('posts', {})
            order = posts_data.get('order', [])
            
            # Кешируем пользователей
            user_cache = {}
            messages = []
            
            for post_id in order:
                if post_id in posts:
                    post = posts[post_id]
                    user_id = post.get('user_id')
                    
                    # Пропускаем сообщения от самого бота
                    if user_id == self.bot_user_id:
                        continue
                    
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
                    
                    # Получаем информацию о канале для названия
                    channel_name = None
                    try:
                        channel_response = self._session_requests.get(
                            f"{self.base_url}/api/v4/channels/{channel_id}",
                            timeout=5
                        )
                        if channel_response.status_code == 200:
                            channel_data = channel_response.json()
                            channel_name = channel_data.get('name', 'unknown')
                    except:
                        channel_name = 'unknown'
                    
                    messages.append({
                        'username': username,
                        'message': post.get('message', ''),
                        'create_at': post.get('create_at', 0),
                        'user_id': user_id,
                        'channel_name': channel_name
                    })
            
            # Сортируем по времени создания
            messages.sort(key=lambda x: x.get('create_at', 0))
            
            return messages
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сообщений канала {channel_id}: {e}")
            return []
    
    async def send_direct_message(self, user_id: str, message: str) -> bool:
        """Отправка личного сообщения пользователю"""
        try:
            # Создаем или получаем канал прямых сообщений
            dm_channel = await self._get_or_create_dm_channel(user_id)
            if not dm_channel:
                logger.error(f"❌ Не удалось создать канал прямых сообщений с {user_id}")
                return False
            
            # Отправляем сообщение
            return await self._send_message(dm_channel['id'], message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки личного сообщения: {e}")
            return False
    
    async def _get_or_create_dm_channel(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получение или создание канала прямых сообщений"""
        try:
            # Попытка создать канал прямых сообщений
            response = self._session_requests.post(
                f"{self.base_url}/api/v4/channels/direct",
                json=[self.bot_user_id, user_id],
                timeout=10
            )
            
            if response.status_code == 200 or response.status_code == 201:
                return response.json()
            else:
                logger.error(f"❌ Ошибка создания канала прямых сообщений: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения канала прямых сообщений: {e}")
            return None
    
    def _is_direct_message(self, channel_id: str) -> bool:
        """Проверяет, является ли канал личным сообщением"""
        try:
            # Получаем информацию о канале
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/channels/{channel_id}",
                timeout=5
            )
            
            if response.status_code == 200:
                channel_data = response.json()
                return channel_data.get('type') == 'D'  # D = Direct message
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки типа канала: {e}")
            return False
    
    async def _handle_direct_message(self, channel_id: str, message: str, user_id: str):
        """Обработка личных сообщений"""
        try:
            # Получаем информацию о пользователе
            user_response = self._session_requests.get(
                f"{self.base_url}/api/v4/users/{user_id}",
                timeout=5
            )
            
            username = "Неизвестный"
            if user_response.status_code == 200:
                user_data = user_response.json()
                username = user_data.get('username', 'Неизвестный')
            
            logger.info(f"📨 Получено личное сообщение от {username}: {message}")
            
            # Проверяем команды управления подписками
            if await self._handle_subscription_commands(channel_id, message, user_id, username):
                return
            
            # Для любого другого сообщения отправляем инструкцию
            await self._send_help_message(channel_id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки личного сообщения: {e}")
    
    async def _handle_subscription_commands(self, channel_id: str, message: str, 
                                         user_id: str, username: str) -> bool:
        """Обработка команд управления подписками"""
        try:
            message_lower = message.lower().strip()
            
            # Проверяем состояние пользователя
            user_state = self._user_states.get(user_id, {})
            
            # Если пользователь в состоянии выбора подписки для удаления
            if user_state.get('action') == 'deleting_subscription':
                await self._handle_subscription_deletion_choice(channel_id, user_id, message)
                return True
            
            if message_lower in ['подписки', 'мои подписки', 'посмотреть подписки']:
                await self._show_subscriptions(channel_id, user_id)
                return True
            
            elif message_lower in ['удалить подписку', 'удалить подписки', 'отписаться']:
                await self._delete_subscription_dialog(channel_id, user_id)
                return True
            
            elif message_lower in ['удалить все подписки', 'удалить все']:
                await self._delete_all_subscriptions(channel_id, user_id)
                return True
            
            elif message_lower.startswith('создать подписку'):
                await self._create_subscription_dialog(channel_id, user_id, username, message)
                return True
            
            elif self._is_subscription_command(message):
                # Распознавание команды подписки в новом формате
                await self._parse_subscription_command(channel_id, user_id, username, message)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки команды подписки: {e}")
            return False
    
    def _is_subscription_command(self, message: str) -> bool:
        """Проверяет, является ли сообщение командой создания подписки"""
        import re
        message_lower = message.lower()
        
        # Проверяем старый формат: канал1,канал2 ~ время ~ частота
        if message.count('~') >= 2:
            parts = message.split('~')
            if len(parts) == 3:
                # Старый формат
                return True
        
        # Проверяем новый формат
        # Должно содержать каналы (~канал или известные названия каналов)
        has_channels = ('~' in message or any(ch in message_lower for ch in 
                       ['general', 'random', 'development', 'qa', 'marketing', 'sales', 'support']))
        
        # Должно содержать время (расширенная проверка)
        has_time = any(word in message_lower for word in ['утра', 'вечера', 'дня', 'ночи']) or \
                   bool(re.search(r'\d{1,2}:\d{2}', message)) or \
                   bool(re.search(r'в\s+\d{1,2}(?:\s|$)', message_lower))
        
        # Должно содержать частоту или день недели (расширенная проверка)
        has_frequency = any(word in message_lower for word in 
                           ['ежедневно', 'каждый день', 'еженедельно', 'каждую неделю', 
                            'каждые', 'daily', 'weekly'])
        
        # Проверяем наличие дней недели (что также указывает на еженедельную подписку)
        has_weekday = any(day in message_lower for day in 
                         ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье',
                          'понедельникам', 'вторникам', 'средам', 'четвергам', 'пятницам', 'субботам', 'воскресеньям'])
        
        # Проверяем паттерны "каждую среду", "каждый понедельник"
        has_weekly_day_pattern = any(pattern in message_lower for pattern in 
                                   ['каждый понедельник', 'каждую вторник', 'каждую среду', 'каждый четверг',
                                    'каждую пятницу', 'каждую субботу', 'каждое воскресенье'])
        
        return has_channels and has_time and (has_frequency or has_weekday or has_weekly_day_pattern)
    
    async def _show_subscriptions(self, channel_id: str, user_id: str):
        """Показать текущие подписки пользователя"""
        try:
            subscriptions = self.subscription_manager.get_user_subscriptions(user_id)
            
            if not subscriptions:
                message = """
📋 **Ваши подписки**

У вас пока нет активных подписок.

**Чтобы создать подписку:**
Отправьте сообщение в одном из форматов:
```
~канал1, ~канал2 ежедневно в 9 утра
~канал1, ~канал2 еженедельно по вторникам в 18:00
~канал1 каждую среду в 6 вечера
~канал1 вторник 18:00
```

**Примеры:**
```
~general, ~random ежедневно в 9 утра
~development, ~qa еженедельно по вторникам в 18:00
~marketing каждую пятницу в 15:30
~support понедельник в 10:00
```

💡 **Важно:** В Mattermost символ `~` необходим для выбора канала!
"""
            else:
                lines = ["📋 **Ваши подписки**\n"]
                
                for i, sub in enumerate(subscriptions, 1):
                    channels = ", ".join(f"~{ch}" for ch in sub['channels'])
                    freq_text = "ежедневно" if sub['frequency'] == 'daily' else "еженедельно"
                    
                    # Добавляем день недели для еженедельных подписок
                    weekday_text = ""
                    if sub['frequency'] == 'weekly' and sub.get('weekday') is not None:
                        weekday_names = ['понедельникам', 'вторникам', 'средам', 'четвергам', 'пятницам', 'субботам', 'воскресеньям']
                        weekday_text = f" по {weekday_names[sub['weekday']]}"
                    
                    lines.append(f"**{i}.** Каналы: {channels}")
                    lines.append(f"   Время: {sub['schedule_time']}")
                    lines.append(f"   Частота: {freq_text}{weekday_text}")
                    lines.append(f"   Создано: {sub['created_at'][:10]}")
                    lines.append("")
                
                lines.append("**Управление подписками:**")
                lines.append("• `удалить подписку` - выбрать подписку для удаления")
                lines.append("• `удалить все подписки` - удалить все подписки сразу")
                lines.append("• `создать подписку` - создать новую подписку")
                lines.append("")
                lines.append("**Примеры новых подписок:**")
                lines.append("• `~general ежедневно в 9 утра`")
                lines.append("• `~random, ~development еженедельно по пятницам в 18:00`")
                lines.append("• `~marketing каждую среду в 15:30`")
                lines.append("• `~support понедельник 10:00`")
                
                message = "\n".join(lines)
            
            await self._send_message(channel_id, message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа подписок: {e}")
    
    async def _create_subscription_dialog(self, channel_id: str, user_id: str, 
                                        username: str, message: str):
        """Диалог создания подписки"""
        try:
            help_message = """
📝 **Создание подписки**

Просто отправьте сообщение в естественном формате:

**Поддерживаемые форматы:**
```
~канал1, ~канал2 ежедневно в 9 утра
~канал1, ~канал2 еженедельно по вторникам в 18:00
~канал1 каждую среду в 6 вечера
~канал1 вторник 18:00
~Канал с пробелами ежедневно в 15:20
```

**Примеры:**
```
~general, ~random ежедневно в 9 утра
~development, ~qa еженедельно по вторникам в 18:00
~marketing каждую пятницу в 15:30
~support понедельник в 10:00
~Тестовый канал ежедневно в 15:20
~Мой канал каждую среду в 18:00
```

**Периодичность:**
• `ежедневно` или `каждый день`
• `еженедельно` или `каждую неделю`
• `каждую среду` или `каждый понедельник`
• Просто `вторник`, `среда`, `пятница` и т.д.

**Время:**
• `в 9 утра` или `в 09:00`
• `в 18:00` или `в 6 вечера`
• `в 15:30` или `в 15`
• просто `18:00`

💡 **Важно:** 
- В Mattermost символ `~` необходим для выбора канала!
- Поддерживаются каналы с пробелами в названии!
- Бот должен быть добавлен во все указанные каналы!
- Добавьте бота командой `/invite @{self.bot_username}`
"""
            
            await self._send_message(channel_id, help_message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка диалога создания подписки: {e}")
    
    async def _delete_subscription_dialog(self, channel_id: str, user_id: str):
        """Диалог удаления подписки - показывает список для выбора"""
        try:
            subscriptions = self.subscription_manager.get_user_subscriptions(user_id)
            
            if not subscriptions:
                await self._send_message(channel_id, """
❌ **Нет подписок для удаления**

У вас нет активных подписок.

Чтобы создать подписку, отправьте сообщение в формате:
```
~канал1, ~канал2 ежедневно в 9 утра
```
""")
                return
            
            # Сохраняем состояние пользователя
            self._user_states[user_id] = {
                'action': 'deleting_subscription',
                'subscriptions': subscriptions
            }
            
            # Формируем сообщение со списком подписок
            lines = ["🗑️ **Выберите подписку для удаления:**\n"]
            
            for i, sub in enumerate(subscriptions, 1):
                channels = ", ".join(f"~{ch}" for ch in sub['channels'])
                freq_text = "ежедневно" if sub['frequency'] == 'daily' else "еженедельно"
                
                # Добавляем день недели для еженедельных подписок
                weekday_text = ""
                if sub['frequency'] == 'weekly' and sub.get('weekday') is not None:
                    weekday_names = ['понедельникам', 'вторникам', 'средам', 'четвергам', 'пятницам', 'субботам', 'воскресеньям']
                    weekday_text = f" по {weekday_names[sub['weekday']]}"
                
                lines.append(f"**{i}.** {channels} - {freq_text}{weekday_text} в {sub['schedule_time']}")
            
            lines.append("")
            lines.append("📝 **Как удалить:**")
            lines.append("• Напишите **номер подписки** (например: `1`)")
            lines.append("• Или напишите `все` для удаления всех подписок")
            lines.append("• Или напишите `отмена` для отмены операции")
            
            message = "\n".join(lines)
            await self._send_message(channel_id, message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка диалога удаления подписки: {e}")
    
    async def _handle_subscription_deletion_choice(self, channel_id: str, user_id: str, message: str):
        """Обработка выбора подписки для удаления"""
        try:
            message_lower = message.lower().strip()
            user_state = self._user_states.get(user_id, {})
            subscriptions = user_state.get('subscriptions', [])
            
            # Очищаем состояние пользователя
            self._user_states.pop(user_id, None)
            
            if message_lower in ['отмена', 'cancel', 'отменить']:
                await self._send_message(channel_id, "❌ **Операция отменена**\n\nУдаление подписки отменено.")
                return
            
            if message_lower in ['все', 'всё', 'all']:
                await self._delete_all_subscriptions(channel_id, user_id)
                return
            
            # Пытаемся получить номер подписки
            try:
                choice_num = int(message_lower)
                if 1 <= choice_num <= len(subscriptions):
                    subscription = subscriptions[choice_num - 1]
                    success = self.subscription_manager.delete_subscription(user_id, subscription['id'])
                    
                    if success:
                        channels = ", ".join(f"~{ch}" for ch in subscription['channels'])
                        await self._send_message(channel_id, f"""
✅ **Подписка удалена**

Подписка на каналы {channels} была успешно удалена.

**Управление подписками:**
• `подписки` - посмотреть оставшиеся подписки
• `удалить подписку` - удалить ещё одну подписку
""")
                    else:
                        await self._send_message(channel_id, "❌ **Ошибка удаления**\n\nНе удалось удалить подписку. Попробуйте позже.")
                else:
                    await self._send_message(channel_id, f"❌ **Неверный номер**\n\nВведите число от 1 до {len(subscriptions)}.")
                    
            except ValueError:
                await self._send_message(channel_id, """
❌ **Неверный формат**

Введите:
• **Номер подписки** (например: `1`)
• `все` для удаления всех подписок
• `отмена` для отмены операции
""")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки выбора удаления: {e}")
            # Очищаем состояние при ошибке
            self._user_states.pop(user_id, None)
    
    async def _delete_all_subscriptions(self, channel_id: str, user_id: str):
        """Удаление всех подписок пользователя"""
        try:
            success = self.subscription_manager.delete_subscription(user_id)
            
            if success:
                message = """
✅ **Все подписки удалены**

Все ваши подписки были успешно удалены.

Чтобы создать новую подписку, отправьте сообщение в формате:
```
~канал1, ~канал2 ежедневно в 9 утра
```

**Примеры:**
```
~general, ~random ежедневно в 9 утра
~development каждую неделю в 18:00
```
"""
            else:
                message = """
❌ **Ошибка удаления**

Не удалось удалить подписки. Попробуйте позже.
"""
            
            await self._send_message(channel_id, message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления всех подписок: {e}")
    
    async def _send_help_message(self, channel_id: str):
        """Отправка справочного сообщения"""
        try:
            help_message = f"""
🤖 **Привет! Я Summary Bot**

Я умею создавать саммари обсуждений в Mattermost и отправлять регулярные сводки по каналам.

**Основные возможности:**

📋 **В каналах:**
• Добавьте меня в канал: `/invite @{self.bot_username}`
• Напишите команду для создания саммари: `!summary`, `summary`, `саммари`, `!саммари`

📊 **Подписки на каналы:**
• Создайте подписку для получения регулярных сводок
• Сводки приходят в личные сообщения по расписанию

**Команды управления подписками:**
• `подписки` - посмотреть текущие подписки
• `удалить подписку` - выбрать подписку для удаления
• `удалить все подписки` - удалить все подписки сразу
• `создать подписку` - получить инструкцию по созданию

**Создание подписки:**
Просто отправьте сообщение в естественном формате:

**Примеры:**
```
~general, ~random ежедневно в 9 утра
~development, ~qa каждую неделю по средам в 18:00
~marketing каждый день в 15:30
```

**Периодичность:**
• `ежедневно` или `каждый день`
• `еженедельно` или `каждую неделю`

💡 **Важно:** 
- В Mattermost символ `~` необходим для выбора канала!
- Для работы с каналами бот должен быть в них добавлен!
- Добавьте меня командой `/invite @{self.bot_username}`

*Для начала работы добавьте меня в нужные каналы и создайте подписку*
"""
            
            await self._send_message(channel_id, help_message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки справки: {e}")
    
    async def _parse_subscription_command(self, channel_id: str, user_id: str, 
                                        username: str, message: str):
        """Парсинг команды создания подписки (поддерживает старый и новый формат)"""
        try:
            # Проверяем формат команды
            if message.count('~') >= 2:
                # Старый формат: канал1,канал2 ~ время ~ частота
                await self._parse_old_format_subscription(channel_id, user_id, username, message)
            else:
                # Новый формат: ~канал1, ~канал2 ежедневно в 9 утра
                await self._parse_new_format_subscription(channel_id, user_id, username, message)
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга команды подписки: {e}")
            await self._send_message(channel_id, "❌ Ошибка обработки команды. Попробуйте позже.")
    
    async def _parse_old_format_subscription(self, channel_id: str, user_id: str, 
                                           username: str, message: str):
        """Парсинг старого формата подписки: канал1,канал2 ~ время ~ частота"""
        try:
            # Формат: канал1,канал2 ~ время ~ частота
            parts = message.split('~')
            
            if len(parts) != 3:
                await self._send_message(channel_id, """
❌ **Неверный формат**

Используйте один из форматов:

**Новый формат (рекомендуется):**
```
~general, ~random ежедневно в 9 утра
~development, ~qa еженедельно по вторникам в 18:00
```

**Старый формат:**
```
general,random ~ 09:00 ~ daily
```
""")
                return
            
            # Парсим части
            channels_str = parts[0].strip()
            time_str = parts[1].strip()
            frequency_str = parts[2].strip().lower()
            
            # Проверяем каналы
            if not channels_str:
                await self._send_message(channel_id, "❌ Укажите хотя бы один канал")
                return
            
            channels = [ch.strip() for ch in channels_str.split(',') if ch.strip()]
            if not channels:
                await self._send_message(channel_id, "❌ Укажите хотя бы один канал")
                return
            
            # Проверяем время
            if not re.match(r'^\d{1,2}:\d{2}$', time_str):
                await self._send_message(channel_id, "❌ Неверный формат времени. Используйте HH:MM")
                return
            
            # Проверяем частоту
            if frequency_str not in ['daily', 'weekly']:
                await self._send_message(channel_id, "❌ Частота должна быть 'daily' или 'weekly'")
                return
            
            # Для старого формата day недели не поддерживаем
            weekday = None
            
            # Создаем подписку (используем общую логику)
            await self._create_subscription(channel_id, user_id, username, channels, time_str, frequency_str, weekday)
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга старого формата: {e}")
            await self._send_message(channel_id, "❌ Ошибка обработки команды. Попробуйте позже.")
    
    async def _parse_new_format_subscription(self, channel_id: str, user_id: str, 
                                           username: str, message: str):
        """Парсинг нового формата подписки: ~канал1, ~канал2 ежедневно в 9 утра"""
        try:
            # Новый формат: ~канал1, ~канал2 ежедневно в 9 утра
            # Или: ~канал1, ~канал2 еженедельно по средам в 15:00
            
            # Парсим каналы (все что начинается с ~ или просто названия каналов)
            channels = self._parse_channels_from_message(message)
            
            if not channels:
                await self._send_message(channel_id, """
❌ **Каналы не найдены**

Укажите каналы в сообщении. В Mattermost для выбора канала используйте символ `~`.

**Примеры:**
```
~general, ~random ежедневно в 9 утра
~development, ~qa еженедельно по вторникам в 18:00
```
""")
                return
            
            # Парсим время из сообщения
            time_str = self._parse_time_from_message(message)
            if not time_str:
                await self._send_message(channel_id, """
❌ **Время не найдено**

Укажите время в сообщении.

**Примеры времени:**
• `в 9 утра` или `в 09:00`
• `в 18:00` или `в 6 вечера`
• `в 15:30` или `в 15`
""")
                return
            
            # Парсим частоту из сообщения
            frequency = self._parse_frequency_from_message(message)
            if not frequency:
                await self._send_message(channel_id, """
❌ **Периодичность не найдена**

Укажите как часто получать сводки.

**Примеры:**
• `ежедневно` или `каждый день`
• `еженедельно` или `каждую неделю`
• `еженедельно по средам` или `каждую неделю по пятницам`
""")
                return
            
            # Парсим день недели (только для еженедельных подписок)
            weekday = None
            if frequency == 'weekly':
                weekday = self._parse_weekday_from_message(message)
            
            # Создаем подписку (используем общую логику)
            await self._create_subscription(channel_id, user_id, username, channels, time_str, frequency, weekday)
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга нового формата: {e}")
            await self._send_message(channel_id, "❌ Ошибка обработки команды. Попробуйте позже.")
    
    async def _create_subscription(self, channel_id: str, user_id: str, username: str, 
                                 channels: List[str], time_str: str, frequency: str, weekday: Optional[int] = None):
        """Общая логика создания подписки"""
        try:
            # Обновляем список каналов перед проверкой доступности
            await self._load_existing_channels()
            
            # Проверяем доступность каналов
            not_found_channels = []
            no_access_channels = []
            
            for channel_name in channels:
                logger.info(f"🔍 Проверяем канал: {channel_name}")
                
                channel_info = await self.get_channel_by_name(channel_name)
                if not channel_info:
                    logger.warning(f"⚠️ Канал не найден: {channel_name}")
                    not_found_channels.append(channel_name)
                    continue
                
                logger.info(f"✅ Канал найден: {channel_info.get('display_name', channel_info.get('name', 'неизвестный'))} (ID: {channel_info['id']})")
                
                if not await self._check_channel_permissions(channel_info['id']):
                    logger.warning(f"⚠️ Нет доступа к каналу: {channel_name} (ID: {channel_info['id']})")
                    no_access_channels.append(channel_name)
                else:
                    logger.info(f"✅ Доступ к каналу подтвержден: {channel_name}")
            
            # Формируем сообщения об ошибках
            if not_found_channels or no_access_channels:
                error_message = "❌ **Проблемы с каналами:**\n\n"
                
                if not_found_channels:
                    channels_list = "\n".join(f"• ~{ch}" for ch in not_found_channels)
                    error_message += f"**Каналы не найдены:**\n{channels_list}\n\n"
                
                if no_access_channels:
                    channels_list = "\n".join(f"• ~{ch}" for ch in no_access_channels)
                    error_message += f"**Нет доступа к каналам:**\n{channels_list}\n\n"
                
                error_message += f"""**Что нужно сделать:**
1. Убедитесь, что названия каналов правильные
2. Добавьте бота в эти каналы командой `/invite @{self.bot_username}`
3. Повторите создание подписки

💡 **Важно:** В Mattermost символ `~` необходим для выбора канала!

**Справка по форматам:**
• ID канала: `~cf787b0d1b9b28356462046be11f699f`
• Внутреннее имя: `~bd-business-development`
• Отображаемое имя: `~Тестовый канал`
"""
                
                await self._send_message(channel_id, error_message)
                return
            
            # Получаем часовой пояс пользователя
            user_timezone = await self.get_user_timezone(user_id)
            if not user_timezone:
                user_timezone = "Europe/Moscow"
            
            # Создаем подписку
            success = self.subscription_manager.create_subscription(
                user_id, username, channels, time_str, frequency, weekday, user_timezone
            )
            
            if success:
                freq_text = "ежедневно" if frequency == 'daily' else "еженедельно"
                channels_text = ", ".join(f"~{ch}" for ch in channels)
                
                # Добавляем день недели для еженедельных подписок
                weekday_text = ""
                if frequency == 'weekly' and weekday is not None:
                    weekday_names = ['понедельникам', 'вторникам', 'средам', 'четвергам', 'пятницам', 'субботам', 'воскресеньям']
                    weekday_text = f" по {weekday_names[weekday]}"
                
                await self._send_message(channel_id, f"""
✅ **Подписка создана!**

**Каналы:** {channels_text}
**Время:** {time_str}
**Частота:** {freq_text}{weekday_text}

Сводки будут приходить в личные сообщения по расписанию.

**Управление подписками:**
• `подписки` - посмотреть текущие подписки
• `удалить подписку` - выбрать подписку для удаления
• `удалить все подписки` - удалить все подписки сразу
""")
            else:
                await self._send_message(channel_id, "❌ Ошибка создания подписки. Попробуйте позже.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания подписки: {e}")
            await self._send_message(channel_id, "❌ Ошибка обработки команды. Попробуйте позже.")
    
    def _parse_channels_from_message(self, message: str) -> List[str]:
        """Извлекает названия каналов из сообщения"""
        channels = []
        
        # Ищем все упоминания каналов с ~ (включая пробелы)
        import re
        
        # Паттерн для поддержки пробелов и русских символов
        # Останавливается на ключевых словах, которые указывают на конец названия канала
        stop_words = ['ежедневно', 'еженедельно', 'каждый', 'каждую', 'каждое', 'в', 'по', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
        stop_pattern = '|'.join(stop_words)
        
        # Ищем каналы по паттерну ~название до стоп-слова или запятой
        channel_pattern = rf'~([a-zA-Z0-9_\-\s\u0400-\u04FF]+?)(?:\s+(?:{stop_pattern})|\s*,|\s*$)'
        matches = re.findall(channel_pattern, message, re.IGNORECASE)
        
        for match in matches:
            clean_match = match.strip()
            if clean_match and clean_match not in channels:
                channels.append(clean_match)
        
        # Если паттерн со стоп-словами не сработал, пробуем простой поиск
        if not channels:
            simple_pattern = r'~([a-zA-Z0-9_\-\s\u0400-\u04FF]+?)(?:\s*,|\s*$)'
            matches = re.findall(simple_pattern, message)
            
            for match in matches:
                clean_match = match.strip()
                if clean_match and clean_match not in channels:
                    channels.append(clean_match)
        
        # Если не найдены каналы с ~, ищем обычные названия каналов
        if not channels:
            # Простой поиск слов, которые могут быть каналами
            words = message.lower().split()
            common_channels = ['general', 'random', 'development', 'qa', 'marketing', 'sales', 'support']
            
            for word in words:
                clean_word = word.strip('.,!?;:')
                if clean_word in common_channels and clean_word not in channels:
                    channels.append(clean_word)
        
        return channels
    
    def _parse_time_from_message(self, message: str) -> str:
        """Извлекает время из сообщения"""
        import re
        
        # Паттерны для времени
        time_patterns = [
            r'в\s+(\d{1,2}):(\d{2})',  # "в 09:00"
            r'в\s+(\d{1,2})\s+утра',    # "в 9 утра"
            r'в\s+(\d{1,2})\s+вечера',  # "в 6 вечера"
            r'в\s+(\d{1,2})\s+дня',     # "в 2 дня"
            r'в\s+(\d{1,2})\s+ночи',    # "в 2 ночи"
            r'в\s+(\d{1,2})(?:\s|$)',   # "в 15" (без указания времени суток)
            r'(\d{1,2}):(\d{2})',       # "18:00" (без "в")
            r'(\d{1,2})\s+утра',        # "9 утра" (без "в")
            r'(\d{1,2})\s+вечера',      # "6 вечера" (без "в")
            r'(\d{1,2})\s+дня',         # "2 дня" (без "в")
            r'(\d{1,2})\s+ночи',        # "2 ночи" (без "в")
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, message.lower())
            if match:
                groups = match.groups()
                if len(groups) == 2:  # Формат HH:MM
                    hour, minute = groups
                    return f"{int(hour):02d}:{int(minute):02d}"
                else:
                    # Формат с указанием времени суток или без указания
                    hour = int(groups[0])
                    
                    if 'вечера' in pattern:
                        if hour <= 11:
                            hour += 12
                    elif 'ночи' in pattern:
                        if hour != 12:
                            hour += 12
                    elif 'утра' in pattern:
                        if hour == 12:
                            hour = 0
                    elif r'в\s+(\d{1,2})(?:\s|$)' in pattern:
                        # "в 15" - без указания времени суток, считаем 24-часовой формат
                        pass  # час остается как есть
                    
                    return f"{hour:02d}:00"
        
        return None
    
    def _parse_frequency_from_message(self, message: str) -> str:
        """Извлекает частоту из сообщения"""
        import re
        message_lower = message.lower()
        
        # Паттерны для ежедневной отправки
        daily_patterns = [
            'ежедневно', 'каждый день', 'каждые сутки', 'daily',
            'каждый день', 'каждое утро', 'каждый вечер'
        ]
        
        # Паттерны для еженедельной отправки
        weekly_patterns = [
            'еженедельно', 'каждую неделю', 'каждые 7 дней', 'weekly',
            'раз в неделю', 'один раз в неделю'
        ]
        
        # Расширенные паттерны для еженедельной отправки с днями недели
        weekly_day_patterns = [
            'каждый понедельник', 'каждый вторник', 'каждую среду', 'каждый четверг',
            'каждую пятницу', 'каждую субботу', 'каждое воскресенье'
        ]
        
        for pattern in daily_patterns:
            if pattern in message_lower:
                return 'daily'
        
        for pattern in weekly_patterns:
            if pattern in message_lower:
                return 'weekly'
        
        for pattern in weekly_day_patterns:
            if pattern in message_lower:
                return 'weekly'
        
        # Если есть день недели и время, но нет явного указания частоты - предполагаем еженедельно
        weekdays = ['понедельник', 'вторник', 'среда', 'среду', 'четверг', 'пятница', 'пятницу', 'суббота', 'субботу', 'воскресенье',
                    'понедельникам', 'вторникам', 'средам', 'четвергам', 'пятницам', 'субботам', 'воскресеньям']
        
        # Проверяем наличие времени
        has_time = any(word in message_lower for word in ['утра', 'вечера', 'дня', 'ночи']) or \
                   bool(re.search(r'\d{1,2}:\d{2}', message)) or \
                   bool(re.search(r'в\s+\d{1,2}(?:\s|$)', message_lower))
        
        if has_time:
            for day in weekdays:
                if day in message_lower:
                    return 'weekly'
        
        return None
    
    def _parse_weekday_from_message(self, message: str) -> int:
        """Извлекает день недели из сообщения"""
        message_lower = message.lower()
        
        # Словарь дней недели (0 = понедельник, 6 = воскресенье)
        weekdays = {
            'понедельник': 0, 'понедельникам': 0, 'пн': 0,
            'вторник': 1, 'вторникам': 1, 'вт': 1,
            'среда': 2, 'средам': 2, 'среду': 2, 'ср': 2,
            'четверг': 3, 'четвергам': 3, 'чт': 3,
            'пятница': 4, 'пятницам': 4, 'пятницу': 4, 'пт': 4,
            'суббота': 5, 'субботам': 5, 'субботу': 5, 'сб': 5,
            'воскресенье': 6, 'воскресеньям': 6, 'вс': 6
        }
        
        # Ищем паттерны с "по"
        for day_name, day_num in weekdays.items():
            if f'по {day_name}' in message_lower:
                return day_num
        
        # Ищем паттерны с "каждую/каждый"
        for day_name, day_num in weekdays.items():
            if f'каждую {day_name}' in message_lower or f'каждый {day_name}' in message_lower or f'каждое {day_name}' in message_lower:
                return day_num
        
        # Ищем просто названия дней
        for day_name, day_num in weekdays.items():
            if day_name in message_lower:
                return day_num
        
        return None 

    async def get_user_timezone(self, user_id: str) -> Optional[str]:
        """Получение часового пояса пользователя через API preferences"""
        try:
            response = self._session_requests.get(
                f"{self.base_url}/api/v4/users/{user_id}/preferences",
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ Ошибка получения настроек пользователя {user_id}: {response.status_code}")
                return None
            
            # Проверяем содержимое ответа
            response_text = response.text
            logger.debug(f"Ответ API preferences для пользователя {user_id}: {response_text}")
            
            if not response_text or response_text.strip() == "" or response_text.strip() == "null":
                logger.info(f"🌍 Настройки пользователя {user_id} пустые, используется Europe/Moscow")
                return None
            
            try:
                preferences = response.json()
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Ошибка парсинга JSON настроек пользователя {user_id}: {e}")
                logger.info(f"🌍 Настройки пользователя {user_id} отсутствуют, используется Europe/Moscow")
                return None
            
            # Проверяем, что preferences это список
            if not isinstance(preferences, list):
                logger.warning(f"⚠️ Неожиданный формат настроек пользователя {user_id}, получен тип: {type(preferences)}")
                logger.debug(f"Содержимое ответа: {preferences}")
                return None
            
            # Ищем preference с timezone
            for preference in preferences:
                if preference.get('category') == 'display_settings' and preference.get('name') == 'timezone':
                    timezone_data = json.loads(preference.get('value', '{}'))
                    timezone = timezone_data.get('automaticTimezone', 
                                               timezone_data.get('manualTimezone', None))
                    if timezone:
                        logger.info(f"🌍 Найден часовой пояс для пользователя {user_id}: {timezone}")
                        return timezone
                    break
            
            logger.info(f"🌍 Часовой пояс для пользователя {user_id} не найден, используется Europe/Moscow")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения часового пояса для пользователя {user_id}: {e}")
            return None