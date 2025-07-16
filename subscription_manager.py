#!/usr/bin/env python3
"""
Менеджер подписок для Mattermost Summary Bot
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz

logger = logging.getLogger(__name__)

class SubscriptionManager:
    """Менеджер для управления подписками пользователей на каналы"""
    
    def __init__(self, db_path: str = "subscriptions.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Инициализация базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Создаем таблицу подписок
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        username TEXT NOT NULL,
                        channels TEXT NOT NULL,
                        schedule_time TEXT NOT NULL,
                        frequency TEXT NOT NULL,
                        weekday INTEGER DEFAULT NULL,
                        timezone TEXT DEFAULT 'UTC',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Добавляем поле weekday, если его нет (миграция)
                cursor.execute("PRAGMA table_info(subscriptions)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'weekday' not in columns:
                    cursor.execute('ALTER TABLE subscriptions ADD COLUMN weekday INTEGER DEFAULT NULL')
                    logger.info("✅ Добавлено поле weekday в таблицу subscriptions")
                
                # Создаем таблицу для логов отправки
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS delivery_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subscription_id INTEGER NOT NULL,
                        delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT NOT NULL,
                        message_count INTEGER DEFAULT 0,
                        error_message TEXT,
                        FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
                    )
                ''')
                
                conn.commit()
                logger.info("✅ База данных подписок инициализирована")
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            raise
    
    def create_subscription(self, user_id: str, username: str, channels: List[str], 
                          schedule_time: str, frequency: str, weekday: int = None, timezone: str = "UTC") -> bool:
        """Создание новой подписки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем, не существует ли уже подписка для этого пользователя
                cursor.execute('''
                    SELECT id FROM subscriptions 
                    WHERE user_id = ? AND is_active = 1
                ''', (user_id,))
                
                existing = cursor.fetchone()
                if existing:
                    # Обновляем существующую подписку
                    cursor.execute('''
                        UPDATE subscriptions 
                        SET channels = ?, schedule_time = ?, frequency = ?, 
                            weekday = ?, timezone = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND is_active = 1
                    ''', (json.dumps(channels), schedule_time, frequency, weekday, timezone, user_id))
                    logger.info(f"✅ Подписка для пользователя {username} обновлена")
                else:
                    # Создаем новую подписку
                    cursor.execute('''
                        INSERT INTO subscriptions (user_id, username, channels, schedule_time, frequency, weekday, timezone)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (user_id, username, json.dumps(channels), schedule_time, frequency, weekday, timezone))
                    logger.info(f"✅ Создана новая подписка для пользователя {username}")
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания подписки: {e}")
            return False
    
    def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """Получение подписок пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, channels, schedule_time, frequency, weekday, timezone, created_at, updated_at
                    FROM subscriptions 
                    WHERE user_id = ? AND is_active = 1
                ''', (user_id,))
                
                subscriptions = []
                for row in cursor.fetchall():
                    subscriptions.append({
                        'id': row[0],
                        'channels': json.loads(row[1]),
                        'schedule_time': row[2],
                        'frequency': row[3],
                        'weekday': row[4],
                        'timezone': row[5],
                        'created_at': row[6],
                        'updated_at': row[7]
                    })
                
                return subscriptions
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения подписок: {e}")
            return []
    
    def delete_subscription(self, user_id: str, subscription_id: Optional[int] = None) -> bool:
        """Удаление подписки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if subscription_id:
                    # Удаляем конкретную подписку
                    cursor.execute('''
                        UPDATE subscriptions 
                        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND user_id = ?
                    ''', (subscription_id, user_id))
                else:
                    # Удаляем все подписки пользователя
                    cursor.execute('''
                        UPDATE subscriptions 
                        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    ''', (user_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка удаления подписки: {e}")
            return False
    
    def get_due_subscriptions(self, current_time: datetime = None) -> List[Dict[str, Any]]:
        """Получение подписок, которые нужно выполнить"""
        if current_time is None:
            current_time = datetime.utcnow()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, user_id, username, channels, schedule_time, frequency, weekday, timezone
                    FROM subscriptions 
                    WHERE is_active = 1
                ''')
                
                due_subscriptions = []
                
                for row in cursor.fetchall():
                    subscription = {
                        'id': row[0],
                        'user_id': row[1],
                        'username': row[2],
                        'channels': json.loads(row[3]),
                        'schedule_time': row[4],
                        'frequency': row[5],
                        'weekday': row[6],
                        'timezone': row[7]
                    }
                    
                    # Проверяем, нужно ли выполнить эту подписку
                    if self._should_execute_subscription(subscription, current_time):
                        due_subscriptions.append(subscription)
                
                return due_subscriptions
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения подписок для выполнения: {e}")
            return []
    
    def _should_execute_subscription(self, subscription: Dict[str, Any], current_time: datetime) -> bool:
        """Проверяет, нужно ли выполнить подписку"""
        try:
            # Конвертируем время в нужный часовой пояс
            user_tz = pytz.timezone(subscription['timezone'])
            user_time = current_time.astimezone(user_tz)
            
            # Парсим время из подписки (формат HH:MM)
            schedule_time_str = subscription['schedule_time']
            hour, minute = map(int, schedule_time_str.split(':'))
            
            # Создаем время выполнения на сегодня
            schedule_time = user_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Проверяем, что время подошло (с точностью до минуты)
            time_diff = abs((user_time - schedule_time).total_seconds())
            if time_diff > 60:  # Больше минуты разница
                return False
            
            # Проверяем частоту выполнения
            frequency = subscription['frequency']
            weekday = subscription.get('weekday')
            
            if frequency == 'daily':
                # Проверяем, была ли уже отправка сегодня
                return not self._was_delivered_today(subscription['id'], user_time)
            elif frequency == 'weekly':
                # Для еженедельных подписок проверяем день недели
                if weekday is not None:
                    # Проверяем, что сегодня именно тот день недели
                    # weekday: 0 = понедельник, 6 = воскресенье
                    if user_time.weekday() != weekday:
                        return False
                
                # Проверяем, была ли отправка на этой неделе
                return not self._was_delivered_this_week(subscription['id'], user_time)
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки выполнения подписки: {e}")
            return False
    
    def _was_delivered_today(self, subscription_id: int, current_time: datetime) -> bool:
        """Проверяет, была ли отправка сегодня"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                cursor.execute('''
                    SELECT id FROM delivery_log 
                    WHERE subscription_id = ? AND status = 'success' 
                    AND delivered_at >= ? AND delivered_at <= ?
                ''', (subscription_id, today_start.isoformat(), today_end.isoformat()))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки отправки за сегодня: {e}")
            return False
    
    def _was_delivered_this_week(self, subscription_id: int, current_time: datetime) -> bool:
        """Проверяет, была ли отправка на этой неделе"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Начало недели (понедельник)
                week_start = current_time - timedelta(days=current_time.weekday())
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                
                cursor.execute('''
                    SELECT id FROM delivery_log 
                    WHERE subscription_id = ? AND status = 'success' 
                    AND delivered_at >= ?
                ''', (subscription_id, week_start.isoformat()))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки отправки за неделю: {e}")
            return False
    
    def log_delivery(self, subscription_id: int, status: str, message_count: int = 0, 
                    error_message: Optional[str] = None):
        """Логирование доставки сводки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO delivery_log (subscription_id, status, message_count, error_message)
                    VALUES (?, ?, ?, ?)
                ''', (subscription_id, status, message_count, error_message))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка логирования доставки: {e}")
    
    def get_all_subscriptions(self) -> List[Dict[str, Any]]:
        """Получение всех активных подписок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, user_id, username, channels, schedule_time, frequency, weekday, timezone, 
                           created_at, updated_at
                    FROM subscriptions 
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                ''')
                
                subscriptions = []
                for row in cursor.fetchall():
                    subscriptions.append({
                        'id': row[0],
                        'user_id': row[1],
                        'username': row[2],
                        'channels': json.loads(row[3]),
                        'schedule_time': row[4],
                        'frequency': row[5],
                        'weekday': row[6],
                        'timezone': row[7],
                        'created_at': row[8],
                        'updated_at': row[9]
                    })
                
                return subscriptions
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения всех подписок: {e}")
            return []
    
    def get_message_collection_period(self, subscription: Dict[str, Any]) -> tuple:
        """
        Определяет период сбора сообщений для подписки с учетом дня недели
        Возвращает (start_time, end_time) в UTC
        """
        try:
            frequency = subscription['frequency']
            timezone = subscription['timezone']
            schedule_time = subscription['schedule_time']
            weekday = subscription.get('weekday')
            
            # Парсим время из подписки
            hour, minute = map(int, schedule_time.split(':'))
            
            # Получаем текущее время в часовом поясе пользователя
            user_tz = pytz.timezone(timezone)
            current_time = datetime.utcnow().astimezone(user_tz)
            
            if frequency == 'daily':
                # Для ежедневных подписок - с вчерашнего времени до сейчас
                yesterday = current_time - timedelta(days=1)
                start_time = yesterday.replace(hour=hour, minute=minute, second=0, microsecond=0)
                end_time = current_time
                
            elif frequency == 'weekly':
                if weekday is not None:
                    # Для еженедельных подписок с указанным днем недели
                    # Находим предыдущий такой же день недели
                    current_weekday = current_time.weekday()
                    days_back = (current_weekday - weekday) % 7
                    
                    # Если сегодня тот же день недели, то берем прошлую неделю
                    if days_back == 0:
                        days_back = 7
                    
                    # Находим начало периода (прошлый такой же день недели в это же время)
                    start_date = current_time - timedelta(days=days_back)
                    start_time = start_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    end_time = current_time
                    
                else:
                    # Для еженедельных подписок без указания дня недели (старая логика)
                    # Берем с прошлой недели
                    start_time = current_time - timedelta(weeks=1)
                    end_time = current_time
                    
            else:
                # Для неизвестной частоты - за последние 24 часа
                start_time = current_time - timedelta(days=1)
                end_time = current_time
            
            # Конвертируем в UTC
            start_time_utc = start_time.astimezone(pytz.UTC)
            end_time_utc = end_time.astimezone(pytz.UTC)
            
            return start_time_utc, end_time_utc
            
        except Exception as e:
            logger.error(f"❌ Ошибка определения периода сбора сообщений: {e}")
            # Возвращаем период за последние 24 часа как fallback
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=1)
            return start_time, end_time 