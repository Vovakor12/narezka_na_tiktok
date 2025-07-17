import whisper
import logging
from typing import Dict, List
import torch

logger = logging.getLogger(__name__)

class AudioTranscriber:
    def __init__(self):
        # Загрузка модели Whisper
        self.model = whisper.load_model("tiny")
        logger.info("Модель Whisper загружена")
    
    async def transcribe(self, audio_path: str) -> Dict:
        """
        Транскрипция аудио с помощью Whisper с пословными таймингами
        """
        try:
            logger.info(f"Начинаю транскрипцию: {audio_path}")
            
            # Транскрипция с word_timestamps для караоке
            result = self.model.transcribe(
                audio_path,
                verbose=True,
                word_timestamps=True,  # Важно для караоке-эффекта
                language=None  # Автоопределение языка
            )
            
            # Форматирование результата
            segments = []
            for segment in result["segments"]:
                # Извлекаем слова с таймингами
                words = []
                if "words" in segment:
                    for word_data in segment["words"]:
                        words.append({
                            "word": word_data.get("word", "").strip(),
                            "start": word_data.get("start", 0),
                            "end": word_data.get("end", 0),
                            "probability": word_data.get("probability", 0)
                        })
                
                segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip(),
                    "confidence": segment.get("avg_logprob", 0),
                    "words": words  # Добавляем пословную информацию
                })
            
            transcription_result = {
                "segments": segments,
                "language": result["language"],
                "duration": result["segments"][-1]["end"] if segments else 0,
                "full_text": result["text"]
            }
            
            logger.info(f"Транскрипция завершена. Найдено {len(segments)} сегментов")
            
            # Логирование для отладки
            for i, seg in enumerate(segments[:3]):  # Первые 3 сегмента для примера
                logger.debug(f"Сегмент {i}: {seg['text'][:50]}... Words: {len(seg.get('words', []))}")
            
            return transcription_result
            
        except Exception as e:
            logger.error(f"Ошибка при транскрипции: {str(e)}")
            raise Exception(f"Не удалось выполнить транскрипцию: {str(e)}")