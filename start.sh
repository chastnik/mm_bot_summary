#!/bin/bash

echo "🤖 Запуск Mattermost Summary Bot..."

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "📋 Создайте файл .env на основе env.example:"
    echo "   cp env.example .env"
    echo "   nano .env"
    exit 1
fi

# Проверяем наличие Docker
if command -v docker-compose &> /dev/null; then
    echo "🐳 Запуск с Docker Compose..."
    docker-compose up -d
    echo "✅ Бот запущен!"
    echo "🌐 Веб-интерфейс: http://localhost:8080"
    echo "📋 Просмотр логов: docker-compose logs -f summary-bot"
elif command -v python3 &> /dev/null; then
    echo "🐍 Запуск с Python..."
    
    # Проверяем виртуальное окружение
    if [ ! -d "venv" ]; then
        echo "📦 Создание виртуального окружения..."
        python3 -m venv venv
    fi
    
    # Активируем виртуальное окружение
    source venv/bin/activate
    
    # Устанавливаем зависимости
    echo "📦 Установка зависимостей..."
    pip install -r requirements.txt
    
    # Запускаем бота
    echo "🚀 Запуск бота..."
    python main.py
else
    echo "❌ Не найден Docker Compose или Python3!"
    echo "📋 Установите одну из систем:"
    echo "   - Docker и Docker Compose"
    echo "   - Python 3.8+"
    exit 1
fi 