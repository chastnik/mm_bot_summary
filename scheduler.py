#!/usr/bin/env python3
"""
Планировщик для автоматической отправки сводок по подпискам
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from subscription_manager import SubscriptionManager
import pytz

if TYPE_CHECKING:
    from mattermost_bot import MattermostBot

logger = logging.getLogger(__name__)

class SubscriptionScheduler:
    """Планировщик для автоматической отправки сводок"""
    
    def __init__(self, bot: 'MattermostBot', subscription_manager: SubscriptionManager):
        self.bot = bot
        self.subscription_manager = subscription_manager
        self._running = False
        self._task = None
    
    async def start(self):
        """Запуск планировщика"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("✅ Планировщик подписок запущен")
    
    async def stop(self):
        """Остановка планировщика"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Планировщик подписок остановлен")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        while self._running:
            try:
                # Проверяем подписки каждую минуту
                await self._check_subscriptions()
                await asyncio.sleep(60)  # Проверка каждые 60 секунд
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в планировщике: {e}")
                await asyncio.sleep(60)
    
    async def _check_subscriptions(self):
        """Проверка и выполнение подписок"""
        try:
            current_time = datetime.utcnow()
            logger.info(f"🔍 Проверка подписок в {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            due_subscriptions = self.subscription_manager.get_due_subscriptions(current_time)
            
            if due_subscriptions:
                logger.info(f"📋 Найдено {len(due_subscriptions)} подписок для выполнения")
                
                for subscription in due_subscriptions:
                    await self._execute_subscription(subscription)
            else:
                logger.info("📋 Нет подписок для выполнения")
        
        except Exception as e:
            logger.error(f"❌ Ошибка проверки подписок: {e}")
    
    async def _execute_subscription(self, subscription: Dict[str, Any]):
        """Выполнение конкретной подписки"""
        try:
            user_id = subscription['user_id']
            username = subscription['username']
            channels = subscription['channels']
            frequency = subscription['frequency']
            subscription_id = subscription['id']
            
            logger.info(f"📤 Выполняю подписку для {username} на каналы: {channels}")
            
            # Проверяем наличие бота в каналах
            missing_channels = []
            available_channels = []
            
            for channel_name in channels:
                channel_info = await self.bot.get_channel_by_name(channel_name)
                if channel_info:
                    channel_id = channel_info['id']
                    if await self.bot._check_channel_permissions(channel_id):
                        available_channels.append((channel_name, channel_id, channel_info))
                    else:
                        missing_channels.append(channel_name)
                else:
                    missing_channels.append(channel_name)
            
            if missing_channels:
                # Уведомляем пользователя о недоступных каналах
                await self._send_channel_access_error(user_id, missing_channels)
                self.subscription_manager.log_delivery(
                    subscription_id, 
                    'error', 
                    0, 
                    f"Нет доступа к каналам: {', '.join(missing_channels)}"
                )
                return
            
            if not available_channels:
                # Нет доступных каналов
                await self._send_no_channels_error(user_id)
                self.subscription_manager.log_delivery(
                    subscription_id, 
                    'error', 
                    0, 
                    "Нет доступных каналов"
                )
                return
            
            # Определяем период для сбора сообщений с учетом дня недели
            since_time, until_time = self.subscription_manager.get_message_collection_period(subscription)
            
            # Собираем сообщения из всех каналов
            all_messages = []
            channel_summaries = []
            
            for channel_name, channel_id, channel_info in available_channels:
                messages = await self.bot.get_channel_messages_since(channel_id, since_time)
                if messages:
                    # Фильтруем сообщения по периоду
                    filtered_messages = []
                    for msg in messages:
                        msg_time = datetime.fromtimestamp(msg.get('create_at', 0) / 1000, tz=pytz.UTC)
                        if since_time <= msg_time <= until_time:
                            filtered_messages.append(msg)
                    
                    if filtered_messages:
                        all_messages.extend(filtered_messages)
                        channel_summaries.append({
                            'channel_name': channel_name,
                            'channel_id': channel_id,
                            'message_count': len(filtered_messages),
                            'display_name': channel_info.get('display_name', channel_name)
                        })
            
            if not all_messages:
                # Нет новых сообщений
                await self._send_no_messages_summary(user_id, channel_summaries, frequency)
                self.subscription_manager.log_delivery(subscription_id, 'success', 0)
                return
            
            # Генерируем сводку
            summary = await self.bot.llm_client.generate_channels_summary(
                all_messages, channel_summaries, frequency
            )
            
            if summary:
                # Отправляем сводку в личные сообщения
                await self._send_summary_to_user(user_id, summary, channel_summaries, frequency)
                self.subscription_manager.log_delivery(subscription_id, 'success', len(all_messages))
                logger.info(f"✅ Сводка для {username} отправлена ({len(all_messages)} сообщений)")
            else:
                # Ошибка генерации сводки
                await self._send_summary_generation_error(user_id, channel_summaries)
                self.subscription_manager.log_delivery(
                    subscription_id, 
                    'error', 
                    len(all_messages), 
                    "Ошибка генерации сводки"
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения подписки: {e}")
            self.subscription_manager.log_delivery(
                subscription_id, 
                'error', 
                0, 
                f"Ошибка выполнения: {str(e)}"
            )
    
    async def _send_summary_to_user(self, user_id: str, summary: str, 
                                       channel_summaries: List[Dict], frequency: str):
        """Отправка сводки пользователю"""
        try:
            # Создаем заголовок
            if frequency == 'daily':
                header = "📊 **Ежедневная сводка каналов**"
            elif frequency == 'weekly':
                header = "📊 **Еженедельная сводка каналов**"
            else:
                header = "📊 **Сводка каналов**"
            
            # Добавляем информацию о каналах
            channels_info = "\n".join([
                f"• **{cs['display_name']}** ({cs['message_count']} сообщений)"
                for cs in channel_summaries
            ])
            
            total_messages = sum(cs['message_count'] for cs in channel_summaries)
            
            message = f"""
{header}

**Каналы:**
{channels_info}

**Всего сообщений:** {total_messages}

---

{summary}

---

💡 *Для управления подписками напишите боту в личку*
"""
            
            await self.bot.send_direct_message(user_id, message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сводки: {e}")
            raise
    
    async def _send_channel_access_error(self, user_id: str, missing_channels: List[str]):
        """Отправка ошибки о недоступности каналов"""
        try:
            channels_list = "\n".join(f"• {channel}" for channel in missing_channels)
            
            message = f"""
❌ **Ошибка доставки сводки**

Бот не может получить доступ к следующим каналам:

{channels_list}

**Что нужно сделать:**
1. Добавьте бота в эти каналы командой `/invite @{self.bot.bot_username}`
2. Либо удалите их из подписки командой `удалить подписку`

💡 *Для управления подписками напишите боту в личку*
"""
            
            await self.bot.send_direct_message(user_id, message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления об ошибке: {e}")
    
    async def _send_no_channels_error(self, user_id: str):
        """Отправка ошибки об отсутствии доступных каналов"""
        try:
            message = f"""
❌ **Ошибка доставки сводки**

Бот не имеет доступа ни к одному из каналов в вашей подписке.

**Что нужно сделать:**
1. Добавьте бота в нужные каналы командой `/invite @{self.bot.bot_username}`
2. Либо создайте новую подписку командой `создать подписку`

💡 *Для управления подписками напишите боту в личку*
"""
            
            await self.bot.send_direct_message(user_id, message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления об ошибке: {e}")
    
    async def _send_no_messages_summary(self, user_id: str, channel_summaries: List[Dict], frequency: str):
        """Отправка уведомления об отсутствии новых сообщений"""
        try:
            if frequency == 'daily':
                period = "за последние 24 часа"
            elif frequency == 'weekly':
                period = "за последнюю неделю"
            else:
                period = "за указанный период"
            
            channels_info = "\n".join([
                f"• **{cs['display_name']}**"
                for cs in channel_summaries
            ])
            
            message = f"""
📊 **Сводка каналов**

**Каналы:**
{channels_info}

ℹ️ В отслеживаемых каналах нет новых сообщений {period}.

💡 *Для управления подписками напишите боту в личку*
"""
            
            await self.bot.send_direct_message(user_id, message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
    
    async def _send_summary_generation_error(self, user_id: str, channel_summaries: List[Dict]):
        """Отправка ошибки генерации сводки"""
        try:
            message = f"""
❌ **Ошибка генерации сводки**

Не удалось создать сводку из-за проблем с AI сервисом.

Попробуйте позже или обратитесь к администратору.

💡 *Для управления подписками напишите боту в личку*
"""
            
            await self.bot.send_direct_message(user_id, message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления об ошибке: {e}") 