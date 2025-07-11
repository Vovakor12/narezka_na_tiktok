from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import os
import json
import uuid
from datetime import datetime
import logging
from dotenv import load_dotenv

from services.video_processor import VideoProcessor
from services.audio_transcriber import AudioTranscriber
from services.video_editor import VideoEditor
from models.schemas import (
    VideoProcessRequest, 
    TranscriptionResponse, 
    HighlightRequest, 
    ProcessingStatus
)
from utils.exceptions import VideoProcessingError
from utils.validators import validate_video_url
from fastapi.responses import FileResponse

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Video Processing API",
    description="API для обработки видео с YouTube/Twitch с генерацией таймкодов и субтитров",
    version="1.0.0"
)

# Инициализация сервисов
video_processor = VideoProcessor()
audio_transcriber = AudioTranscriber()
video_editor = VideoEditor()

# Хранилище задач (в продакшене лучше использовать Redis)
tasks_storage = {}

@app.post("/api/v1/process-video", response_model=dict)
async def process_video(
    request: VideoProcessRequest,
    background_tasks: BackgroundTasks
):
    """
    Первый этап: обработка видео и извлечение таймкодов с текстом
    """
    try:
        # Валидация URL
        validate_video_url(request.video_url)
        
        # Генерация уникального ID задачи
        task_id = str(uuid.uuid4())
        
        # Сохранение статуса задачи
        tasks_storage[task_id] = {
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "video_url": request.video_url
        }
        
        # Запуск фоновой задачи
        background_tasks.add_task(
            process_video_background, 
            task_id, 
            request.video_url
        )
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Видео поставлено в очередь на обработку"
        }
        
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    Получение статуса задачи
    """
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    return tasks_storage[task_id]

@app.get("/api/v1/transcription/{task_id}")
async def get_transcription(task_id: str):
    """
    Получение результата транскрипции
    """
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task = tasks_storage[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Задача ещё не завершена")
    
    if "transcription" not in task:
        raise HTTPException(status_code=404, detail="Транскрипция не найдена")
    
    return task["transcription"]

@app.post("/api/v1/create-highlights")
async def create_highlights(
    request: HighlightRequest,
    background_tasks: BackgroundTasks
):
    """
    Второй этап: создание видео с лучшими моментами
    """
    try:
        # Проверка существования оригинальной задачи
        if request.original_task_id not in tasks_storage:
            raise HTTPException(status_code=404, detail="Оригинальная задача не найдена")
        
        original_task = tasks_storage[request.original_task_id]
        if original_task["status"] != "completed":
            raise HTTPException(status_code=400, detail="Оригинальная задача не завершена")
        
        # Генерация нового ID для задачи создания хайлайтов
        highlight_task_id = str(uuid.uuid4())
        
        tasks_storage[highlight_task_id] = {
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "type": "highlight_creation",
            "original_task_id": request.original_task_id
        }
        
        # Запуск фоновой задачи создания хайлайтов
        background_tasks.add_task(
            create_highlights_background,
            highlight_task_id,
            request.original_task_id,
            request.highlights
        )
        
        return {
            "task_id": highlight_task_id,
            "status": "processing",
            "message": "Создание хайлайтов запущено"
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании хайлайтов: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/download/{task_id}")
async def download_video(task_id: str):
    """
    Скачивание готового архива хайлайтов
    """
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    task = tasks_storage[task_id]
    if task["status"] != "completed" or "output_file" not in task:
        raise HTTPException(status_code=400, detail="Задача ещё не завершена или файл не найден")

    file_path = task["output_file"]
    
    if not isinstance(file_path, str):
        raise HTTPException(status_code=500, detail="Неверный формат пути к файлу")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type="application/zip"
    )

async def process_video_background(task_id: str, video_url: str):
    """
    Фоновая задача обработки видео
    """
    try:
        logger.info(f"Начинаю обработку видео {video_url}")
        
        # Скачивание видео
        video_path = await video_processor.download_video(video_url)
        
        # Извлечение аудио
        audio_path = await video_processor.extract_audio(video_path)
        
        # Транскрипция
        transcription = await audio_transcriber.transcribe(audio_path)
        
        # Обновление статуса
        tasks_storage[task_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "transcription": transcription,
            "video_path": video_path,
            "audio_path": audio_path
        })
        
        logger.info(f"Обработка видео {task_id} завершена")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке видео {task_id}: {str(e)}")
        tasks_storage[task_id].update({
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })

async def create_highlights_background(
    highlight_task_id: str, 
    original_task_id: str, 
    highlights: List[dict]
):
    """
    Фоновая задача создания хайлайтов
    """
    try:
        logger.info(f"Создаю хайлайты для задачи {original_task_id}")
        
        original_task = tasks_storage[original_task_id]
        video_path = original_task["video_path"]
        transcription = original_task["transcription"]
        
        # Создание видео с хайлайтами
        output_path = await video_editor.create_highlights(
            video_path,
            highlights,
            transcription
        )
        
        # Обновление статуса
        tasks_storage[highlight_task_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "output_file": output_path
        })
        
        logger.info(f"Хайлайты для задачи {highlight_task_id} созданы")
        
    except Exception as e:
        logger.error(f"Ошибка при создании хайлайтов {highlight_task_id}: {str(e)}")
        tasks_storage[highlight_task_id].update({
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })

@app.get("/")
async def root():
    return {"message": "Video Processing API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)