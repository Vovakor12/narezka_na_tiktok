# models/schemas.py
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime

class VideoProcessRequest(BaseModel):
    video_url: HttpUrl
    language: Optional[str] = "auto"

class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: Optional[float] = None

class TranscriptionResponse(BaseModel):
    segments: List[TranscriptionSegment]
    language: str
    duration: float

class HighlightSegment(BaseModel):
    start_time: float
    end_time: float
    title: Optional[str] = None
    description: Optional[str] = None

class HighlightRequest(BaseModel):
    original_task_id: str
    highlights: List[HighlightSegment]

class ProcessingStatus(BaseModel):
    task_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None