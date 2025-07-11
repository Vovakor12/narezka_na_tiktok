class VideoProcessingError(Exception):
    """Базовое исключение для ошибок обработки видео"""
    pass

class VideoDownloadError(VideoProcessingError):
    """Ошибка скачивания видео"""
    pass

class AudioExtractionError(VideoProcessingError):
    """Ошибка извлечения аудио"""
    pass

class TranscriptionError(VideoProcessingError):
    """Ошибка транскрипции"""
    pass