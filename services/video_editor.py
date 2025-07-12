import os
from pathlib import Path
import subprocess
import logging
from typing import List, Dict, Tuple
from uuid import uuid4
import zipfile
import json
from models.schemas import HighlightSegment

logger = logging.getLogger(__name__)


class VideoEditor:
    def __init__(self):
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "./outputs"))
        self.output_dir.mkdir(exist_ok=True)
        
        # Параметры для TikTok формата
        self.tiktok_width = 1080
        self.tiktok_height = 1920
        self.tiktok_aspect = "9:16"
        
    async def create_highlights(
        self,
        video_path: str,
        highlights: List[HighlightSegment],
        transcription: Dict
    ) -> str:
        try:
            if not highlights:
                raise ValueError("Список хайлайтов пуст")

            video_path = Path(video_path)
            task_id = uuid4().hex
            work_dir = self.output_dir / task_id
            work_dir.mkdir(exist_ok=True)

            # Получаем информацию о видео
            video_info = await self._get_video_info(str(video_path))
            
            output_paths = []

            for i, highlight in enumerate(highlights):
                clip_path = work_dir / f"highlight_{i}_{video_path.stem}_tiktok.mp4"
                
                # Создаем видео с кадрированием и субтитрами
                await self._create_tiktok_clip(
                    video_path=str(video_path),
                    output_path=str(clip_path),
                    start_time=highlight.start_time,
                    end_time=highlight.end_time,
                    transcription=transcription,
                    video_info=video_info
                )
                
                output_paths.append(clip_path)
                logger.info(f"Создан клип {i+1}/{len(highlights)}")

            # Создаём zip-архив
            zip_path = self.output_dir / f"highlights_{video_path.stem}_{task_id}.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for path in output_paths:
                    zipf.write(path, arcname=path.name)

            logger.info(f"ZIP с хайлайтами создан: {zip_path}")
            return str(zip_path)

        except Exception as e:
            logger.error(f"Ошибка при создании хайлайтов: {str(e)}")
            raise Exception(f"Не удалось создать хайлайты: {str(e)}")

    async def _get_video_info(self, video_path: str) -> Dict:
        """Получение информации о видео"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,avg_frame_rate',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"FFprobe error: {result.stderr}")
            
        info = json.loads(result.stdout)
        stream = info['streams'][0]
        
        # Парсим FPS
        fps_parts = stream['avg_frame_rate'].split('/')
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30
        
        return {
            'width': int(stream['width']),
            'height': int(stream['height']),
            'fps': fps
        }

    async def _create_tiktok_clip(
        self,
        video_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
        transcription: Dict,
        video_info: Dict
    ):
        """Создание клипа в формате TikTok с красивыми субтитрами"""
        
        # Создаем сложный фильтр для FFmpeg
        filter_complex = []
        
        # 1. Кадрирование и масштабирование для TikTok формата
        crop_filter = self._create_smart_crop_filter(video_info)
        filter_complex.append(crop_filter)
        
        # 2. Добавляем субтитры
        subtitle_filters = await self._create_subtitle_filters(
            transcription, start_time, end_time
        )
        
        # Объединяем все фильтры
        full_filter = ",".join(filter_complex + subtitle_filters)
        
        # Команда FFmpeg
        cmd = [
            'ffmpeg',
            '-ss', str(start_time),
            '-to', str(end_time),
            '-i', video_path,
            '-vf', full_filter,
            '-c:v', 'libx264',  # Используем x264 для совместимости
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',  # Для быстрого старта воспроизведения
            '-y',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode != 0:
            raise Exception(f"FFmpeg error: {result.stderr}")

    def _create_smart_crop_filter(self, video_info: Dict) -> str:
        """Создание фильтра для умного кадрирования"""
        input_width = video_info['width']
        input_height = video_info['height']
        
        # Рассчитываем размеры для кадрирования
        target_aspect = self.tiktok_width / self.tiktok_height
        current_aspect = input_width / input_height
        
        if current_aspect > target_aspect:
            # Видео слишком широкое - обрезаем по бокам
            new_width = int(input_height * target_aspect)
            new_height = input_height
            # Центрируем по горизонтали
            x_offset = (input_width - new_width) // 2
            y_offset = 0
        else:
            # Видео слишком высокое - обрезаем сверху/снизу
            new_width = input_width
            new_height = int(input_width / target_aspect)
            x_offset = 0
            # Фокусируемся на верхней части (обычно там важный контент)
            y_offset = 0
        
        # Создаем фильтр кадрирования и масштабирования
        crop_filter = f"crop={new_width}:{new_height}:{x_offset}:{y_offset}"
        scale_filter = f"scale={self.tiktok_width}:{self.tiktok_height}"
        
        return f"{crop_filter},{scale_filter}"

    async def _create_subtitle_filters(
        self,
        transcription: Dict,
        start_time: float,
        end_time: float
    ) -> List[str]:
        """Создание красивых субтитров с помощью drawtext"""
        filters = []
        
        # Находим релевантные сегменты
        relevant_segments = []
        for segment in transcription["segments"]:
            if segment["start"] >= start_time and segment["end"] <= end_time:
                relevant_segments.append({
                    "start": segment["start"] - start_time,
                    "end": segment["end"] - start_time,
                    "text": segment["text"].strip()
                })
        
        # Стили для субтитров
        font_file = "ofont.ru_Liberation Sans.ttf"
        font_size = 48
        font_color = "white"
        border_color = "black"
        border_width = 4
        
        # Создаем фильтры drawtext для каждого сегмента
        for i, segment in enumerate(relevant_segments):
            # Экранируем специальные символы
            text = segment["text"].replace("'", "\\'").replace(":", "\\:")
            
            # Разбиваем длинный текст на строки
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                current_line.append(word)
                if len(" ".join(current_line)) > 30:  # Максимум 30 символов в строке
                    lines.append(" ".join(current_line[:-1]))
                    current_line = [word]
            
            if current_line:
                lines.append(" ".join(current_line))
            
            # Объединяем строки с переносом
            formatted_text = "\\n".join(lines)
            
            # Создаем фильтр drawtext
            drawtext_filter = (
                f"drawtext="
                f"text='{formatted_text}':"
                f"fontfile={font_file}:"
                f"fontsize={font_size}:"
                f"fontcolor={font_color}:"
                f"bordercolor={border_color}:"
                f"borderw={border_width}:"
                f"x=(w-text_w)/2:"  # Центрирование по горизонтали
                f"y=h-text_h-50:"    # Отступ снизу 50 пикселей
                f"enable='between(t,{segment['start']},{segment['end']})'"
            )
            
            filters.append(drawtext_filter)
        
        return filters

    def _format_time(self, seconds: float) -> str:
        """Форматирование времени для SRT"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"