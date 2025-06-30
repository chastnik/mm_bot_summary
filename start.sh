#!/bin/bash

# 🚀 Mattermost Summary Bot - Стартовый скрипт
echo "🤖 Запуск Mattermost Summary Bot..."

# Проверка файла конфигурации
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    echo "📝 Создайте .env на основе env.example:"
    echo "   cp env.example .env"
    echo "   nano .env"
    exit 1
fi

# Активация виртуального окружения
if [ -d "venv" ]; then
    echo "🔧 Активация виртуального окружения..."
    source venv/bin/activate
else
    echo "⚠️ Виртуальное окружение не найдено"
    echo "📦 Создание venv..."
    python -m venv venv
    source venv/bin/activate
    echo "📦 Установка зависимостей..."
    pip install -r requirements.txt
fi

# Проверка зависимостей
echo "📦 Проверка зависимостей..."
pip install -r requirements.txt --quiet

# Запуск основного приложения
echo "🚀 Запуск бота..."
echo "🌐 Веб-интерфейс: http://localhost:8080"
echo "📊 API документация: http://localhost:8080/docs"
echo "❤️ Health check: http://localhost:8080/health"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

python main.py 