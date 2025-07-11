import logging
from typing import Dict
import torch
import torchaudio
from transformers import AutoProcessor, AutoModel
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioTranscriber:
    def __init__(self):
        try:
            self.processor = AutoProcessor.from_pretrained(
                "waveletdeboshir/gigaam-rnnt",
                trust_remote_code=True
            )
            self.model = AutoModel.from_pretrained(
                "waveletdeboshir/gigaam-rnnt",
                trust_remote_code=True
            )
            self.model.eval()
            logger.info("Модель GigaAM успешно загружена.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке модели GigaAM: {e}")
            raise Exception("Не удалось инициализировать модель GigaAM")

    async def transcribe(self, audio_path: str) -> Dict:
        try:
            logger.info(f"Транскрипция аудио: {audio_path}")
            audio_path = Path(audio_path).resolve().as_posix()
            # Загрузка и ресемплирование
            waveform, sample_rate = torchaudio.load(audio_path)
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                waveform = resampler(waveform)
            waveform = waveform.squeeze()

            # Подготовка входа
            inputs = self.processor(waveform, sampling_rate=16000, return_tensors="pt")

            with torch.no_grad():
                outputs = self.model(**inputs)
                predicted_ids = torch.argmax(outputs.logits, dim=-1)
                transcription = self.processor.batch_decode(predicted_ids)[0]

            duration = waveform.shape[-1] / 16000.0

            return {
                "segments": [{
                    "start": 0.0,
                    "end": duration,
                    "text": transcription,
                    "confidence": None
                }],
                "language": "ru",
                "duration": duration,
                "full_text": transcription
            }

        except Exception as e:
            logger.error(f"Ошибка при транскрипции: {e}")
            raise Exception(f"Не удалось выполнить транскрипцию: {e}")