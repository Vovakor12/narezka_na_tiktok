import os
import yt_dlp
import subprocess
from pathlib import Path
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", "./uploads"))
        self.upload_dir.mkdir(exist_ok=True)
        self.cookies_file = os.getenv("COOKIES_FILE", "./cookies.txt")

    async def download_video(self, video_url: str) -> str:
        """
        Скачивание видео с YouTube/Twitch с поддержкой cookies
        """
        try:
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': str(self.upload_dir / '%(title)s.%(ext)s'),
                'max_filesize': 500_000_000,
            }

            if os.path.exists(self.cookies_file):
                logger.info(f"Используются cookies из {self.cookies_file}")
                ydl_opts['cookiefile'] = self.cookies_file
            else:
                logger.warning("Файл cookies не найден. Продолжаю без авторизации.")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                filename = ydl.prepare_filename(info)
                ydl.download([video_url])
                logger.info(f"Видео скачано: {filename}")
                return filename

        except Exception as e:
            logger.error(f"Ошибка при скачивании видео: {str(e)}")
            raise Exception(f"Не удалось скачать видео: {str(e)}")

    async def extract_audio(self, video_path: str) -> str:
        """
        Извлечение аудио из видео
        """
        try:
            video_path = Path(video_path)
            audio_path = video_path.with_suffix('.wav')
            
            # Извлечение аудио с помощью ffmpeg
            cmd = [
                'ffmpeg', '-i', str(video_path),
                '-ar', '16000',  # Частота дискретизации 16kHz
                '-ac', '1',      # Моно
                '-c:a', 'pcm_s16le',
                str(audio_path),
                '-y'  # Перезаписать файл
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg error: {result.stderr}")
            
            logger.info(f"Аудио извлечено: {audio_path}")
            return str(audio_path)
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении аудио: {str(e)}")
            raise Exception(f"Не удалось извлечь аудио: {str(e)}")