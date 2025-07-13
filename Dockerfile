FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    curl \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Установка рабочей директории
WORKDIR /app

# Копирование и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Предварительная загрузка модели Whisper для оптимизации
RUN python -c "import whisper; whisper.load_model('medium')"

# Копирование кода приложения
COPY . .

# Создание необходимых директорий
RUN mkdir -p uploads outputs logs && \
    chown -R appuser:appuser /app

# Копирование шрифта для субтитров (если есть)
RUN if [ -f "ofont.ru_Liberation Sans.ttf" ]; then \
        mkdir -p /usr/share/fonts/truetype/liberation && \
        cp "ofont.ru_Liberation Sans.ttf" /usr/share/fonts/truetype/liberation/ && \
        fc-cache -fv; \
    fi

# Переключение на непривилегированного пользователя
USER appuser

# Установка переменных окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose порт
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Команда по умолчанию
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]