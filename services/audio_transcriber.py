import whisper
import logging
from typing import Dict, List
import torch

logger = logging.getLogger(__name__)

class AudioTranscriber:
    def __init__(self):
        # Загрузка модели Whisper
        self.model = whisper.load_model("medium")
        logger.info("Модель Whisper загружена")
    
    async def transcribe(self, audio_path: str) -> Dict:
        """
        Транскрипция аудио с помощью Whisper
        """
        try:
            logger.info(f"Начинаю транскрипцию: {audio_path}")
            
            # Транскрипция
            result = self.model.transcribe(
                audio_path,
                verbose=True,
                word_timestamps=True
            )
            
            # Форматирование результата
            segments = []
            for segment in result["segments"]:
                segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip(),
                    "confidence": segment.get("avg_logprob", 0)
                })
            
            transcription_result = {
                "segments": segments,
                "language": result["language"],
                "duration": result["segments"][-1]["end"] if segments else 0,
                "full_text": result["text"]
            }
            
            logger.info(f"Транскрипция завершена. Найдено {len(segments)} сегментов")
            return transcription_result
            
        except Exception as e:
            logger.error(f"Ошибка при транскрипции: {str(e)}")
            raise Exception(f"Не удалось выполнить транскрипцию: {str(e)}")