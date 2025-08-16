import os
from typing import List


class Config:
    # 支持的文件格式
    SUPPORTED_VIDEO_FORMATS: List[str] = ["mp4", "avi", "mov", "mkv"]
    SUPPORTED_AUDIO_FORMATS: List[str] = ["mp3", "wav", "aac", "flac"]
    
    # 文件大小限制（字节）
    MAX_FILE_SIZE: int = 1 * 1024 * 1024 * 1024  # 1GB
    
    # 支持的语言
    SUPPORTED_LANGUAGES: List[str] = ["en", "zh", "es", "fr", "de"]
    
    # API 配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GOOGLE_TRANSLATE_API_KEY: str = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
    
    # 作业状态管理配置
    JOB_STATE_FILE: str = os.getenv("JOB_STATE_FILE", "./job_states.json")
    JOB_STATE_SAVE_INTERVAL: int = int(os.getenv("JOB_STATE_SAVE_INTERVAL", "30"))  # 秒
    
    # 文件存储路径
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./outputs")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "./temp")
    
    # 音频处理配置
    AUDIO_SAMPLE_RATE: int = 48000
    AUDIO_BIT_DEPTH: int = 16