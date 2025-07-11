import re
from urllib.parse import urlparse
from fastapi import HTTPException

def validate_video_url(url: str) -> bool:
    """
    Валидация URL видео YouTube/Twitch
    """
    youtube_pattern = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    twitch_pattern = r'(https?://)?(www\.)?twitch\.tv/'
    
    if not (re.match(youtube_pattern, url) or re.match(twitch_pattern, url)):
        raise HTTPException(
            status_code=400, 
            detail="Поддерживаются только ссылки на YouTube и Twitch"
        )
    
    return True