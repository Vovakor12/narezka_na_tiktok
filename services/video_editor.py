import os
from pathlib import Path
import subprocess
import logging
from typing import List, Dict
from uuid import uuid4
import zipfile
import json
import re
from models.schemas import HighlightSegment

logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "./outputs"))
        self.output_dir.mkdir(exist_ok=True)
        
        # Параметры для TikTok формата
        self.tiktok_width = 1080
        self.tiktok_height = 1920
        
    async def create_highlights(
        self,
        video_path: str,
        highlights: List[HighlightSegment],
        transcription: Dict
    ) -> str:
        try:
            video_path = Path(video_path)
            task_id = uuid4().hex
            work_dir = self.output_dir / task_id
            work_dir.mkdir(exist_ok=True)

            output_paths = []

            for i, highlight in enumerate(highlights):
                clip_path = work_dir / f"highlight_{i}_{video_path.stem}_tiktok.mp4"
                
                # Создаем видео с субтитрами и караоке-эффектом
                await self._create_simple_clip(
                    video_path=str(video_path),
                    output_path=str(clip_path),
                    start_time=highlight.start_time,
                    end_time=highlight.end_time,
                    transcription=transcription
                )
                
                output_paths.append(clip_path)
                logger.info(f"Создан клип {i+1}/{len(highlights)}")

            # Создаём zip-архив
            zip_path = self.output_dir / f"highlights_{video_path.stem}_{task_id}.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for path in output_paths:
                    zipf.write(path, arcname=path.name)

            logger.info(f"ZIP создан: {zip_path}")
            return str(zip_path)

        except Exception as e:
            logger.error(f"Ошибка: {str(e)}")
            raise

    async def _create_simple_clip(
        self,
        video_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
        transcription: Dict
    ):
        """Создание клипа с субтитрами и караоке-эффектом"""
        
        # Создаем ASS файл с субтитрами и караоке-эффектом
        ass_path = Path(output_path).parent / f"{Path(output_path).stem}.ass"
        self._create_ass_file(transcription, start_time, end_time, ass_path)
        
        # Ensure the ASS file exists
        if not ass_path.exists():
            logger.error(f"ASS file not found: {ass_path}")
            raise Exception(f"ASS file not found: {ass_path}")

        # Format the subtitle path for FFmpeg (use forward slashes and escape spaces)
        ass_path_str = str(ass_path).replace('\\', '/').replace(' ', '\\ ')
        
        # Команда FFmpeg с ASS субтитрами
        cmd = [
            'ffmpeg',
            '-ss', str(start_time),
            '-to', str(end_time),
            '-i', video_path,
            '-vf', (
                f"crop=ih*9/16:ih:iw/2-ih*9/32:0,"
                f"scale={self.tiktok_width}:{self.tiktok_height},"
                f"subtitles='{ass_path_str}'"
            ),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            output_path
        ]
        
        # Log the FFmpeg command for debugging
        logger.info(f"Запуск FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        # Удаляем временный ASS файл
        if ass_path.exists():
            ass_path.unlink()
        
        if result.returncode != 0:
            logger.error(f"FFmpeg stderr: {result.stderr}")
            raise Exception(f"FFmpeg error: {result.stderr}")

    def _create_ass_file(
        self,
        transcription: Dict,
        start_time: float,
        end_time: float,
        ass_path: Path
    ):
        """Создание ASS файла с субтитрами и караоке-эффектом для целых фраз"""
        
        # Фильтруем релевантные сегменты
        relevant_segments = []
        for segment in transcription["segments"]:
            if segment["end"] > start_time and segment["start"] < end_time:
                segment_start = max(0, segment["start"] - start_time)
                segment_end = min(end_time - start_time, segment["end"] - start_time)
                words = []
                if "words" in segment:
                    for word in segment["words"]:
                        word_start = max(0, word["start"] - start_time)
                        word_end = min(end_time - start_time, word["end"] - start_time)
                        if word_start < word_end:
                            words.append({
                                "start": word_start,
                                "end": word_end,
                                "text": self._clean_text(word["word"])
                            })
                relevant_segments.append({
                    "start": segment_start,
                    "end": segment_end,
                    "words": words
                })
        
        # Создаем ASS содержимое
        ass_content = [
            "[Script Info]",
            "Title: Karaoke Subtitles",
            "ScriptType: v4.00+",
            "Collisions: Normal",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Karaoke,Arial,40,&H00FFFFFF,&H00808080,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,50,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]
        
        for i, segment in enumerate(relevant_segments, 1):
            if not segment["words"]:  # Пропускаем пустые сегменты
                continue
            # Создаем текст с караоке-тегами для каждого слова
            karaoke_text = ""
            for word in segment["words"]:
                duration_centisec = int((word["end"] - word["start"]) * 100)  # Длительность в сотых секунды
                karaoke_text += f"{{\\k{duration_centisec}}}{word['text']} "
            karaoke_text = karaoke_text.rstrip()  # Удаляем конечный пробел
            start_time_str = self._format_ass_time(segment["start"])
            end_time_str = self._format_ass_time(segment["end"])
            ass_content.append(
                f"Dialogue: 0,{start_time_str},{end_time_str},Karaoke,,0,0,0,,{karaoke_text}"
            )
        
        # Log ASS content for debugging
        logger.debug(f"ASS content:\n{'\n'.join(ass_content)}")
        
        # Записываем файл
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(ass_content))
        logger.info(f"ASS file created: {ass_path}")

    def _clean_text(self, text: str) -> str:
        """Очистка текста"""
        text = ' '.join(text.split())
        text = text.replace('\\n', ' ').replace('\n', ' ')
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[{}]', '', text)  # Удаляем специальные символы ASS
        return text.strip()

    def _split_text_simple(self, text: str, max_length: int = 30) -> List[str]:
        """Простое разбиение текста на строки"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            current_line.append(word)
            if len(' '.join(current_line)) > max_length:
                if len(current_line) > 1:
                    current_line.pop()
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines[:2]  # Максимум 2 строки

    def _format_ass_time(self, seconds: float) -> str:
        """Форматирование времени для ASS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        centisecs = int((secs % 1) * 100)
        secs = int(secs)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    async def _get_video_info(self, video_path: str) -> Dict:
        """Получение информации о видео"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            stream = info['streams'][0]
            return {
                'width': int(stream['width']),
                'height': int(stream['height'])
            }
        return {'width': 1920, 'height': 1080}  # Значения по умолчанию