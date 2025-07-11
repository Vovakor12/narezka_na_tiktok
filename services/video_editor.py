import os
from pathlib import Path
import subprocess
import logging
from typing import List, Dict
from uuid import uuid4
import zipfile
from models.schemas import HighlightSegment

logger = logging.getLogger(__name__)


class VideoEditor:
    def __init__(self):
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "./outputs"))
        self.output_dir.mkdir(exist_ok=True)

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

            output_paths = []

            for i, highlight in enumerate(highlights):
                clip_path = work_dir / f"highlight_{i}_{video_path.stem}.mp4"
                srt_path = await self._create_subtitles_for_segment(transcription, highlight, work_dir, i)

                cmd = [
                    'ffmpeg',
                    '-ss', str(highlight.start_time),
                    '-to', str(highlight.end_time),
                    '-i', str(video_path),
                    '-vf', f"subtitles='{srt_path.as_posix()}'",
                    '-c:v', 'libx264',  # или 'h264_nvenc' если доступен
                    '-c:a', 'aac',
                    str(clip_path),
                    '-y'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
                if result.returncode != 0:
                    raise Exception(f"FFmpeg error: {result.stderr}")

                output_paths.append(clip_path)

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

    async def _create_subtitles_for_segment(
        self,
        transcription: Dict,
        highlight: HighlightSegment,
        work_dir: Path,
        index: int
    ) -> Path:
        srt_path = work_dir / f"subtitles_{index}.srt"
        relevant_segments = []

        for segment in transcription["segments"]:
            if segment["start"] >= highlight.start_time and segment["end"] <= highlight.end_time:
                shifted_segment = {
                    "start": segment["start"] - highlight.start_time,
                    "end": segment["end"] - highlight.start_time,
                    "text": segment["text"]
                }
                relevant_segments.append(shifted_segment)

        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(relevant_segments, 1):
                start_time = self._format_time(segment["start"])
                end_time = self._format_time(segment["end"])
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{segment['text']}\n\n")

        return srt_path

    def _format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
