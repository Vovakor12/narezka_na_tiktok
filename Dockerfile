FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание директорий
RUN mkdir -p uploads outputs

# Запуск приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# deploy.sh
#!/bin/bash

# Скрипт для деплоя на сервер

echo "Деплой Video Processing API..."

# Остановка старых контейнеров
docker-compose down

# Сборка новых образов
docker-compose build

# Запуск сервисов
docker-compose up -d

echo "Деплой завершен!"
echo "API доступен по адресу: http://localhost:8000"
echo "Документация: http://localhost:8000/docs"