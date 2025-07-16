#!/bin/bash

# 🚀 Mattermost Summary Bot - Стартовый скрипт
echo "🤖 Запуск Mattermost Summary Bot..."

# Функция для определения доступной команды Python
get_python_cmd() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        echo "❌ Python не найден в системе!"
        echo "📦 Установите Python 3.8+ и повторите попытку"
        exit 1
    fi
}

# Функция для определения доступной команды pip
get_pip_cmd() {
    if command -v pip3 &> /dev/null; then
        echo "pip3"
    elif command -v pip &> /dev/null; then
        echo "pip"
    else
        echo "❌ pip не найден в системе!"
        echo "📦 Установите pip и повторите попытку"
        exit 1
    fi
}

# Получение команд
PYTHON_CMD=$(get_python_cmd)
PIP_CMD=$(get_pip_cmd)

echo "🐍 Используется: $PYTHON_CMD"
echo "📦 Используется: $PIP_CMD"

# Проверка версии Python
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
echo "🔢 Версия Python: $PYTHON_VERSION"

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
    $PYTHON_CMD -m venv venv
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