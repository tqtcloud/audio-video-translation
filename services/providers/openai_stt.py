import os
import time
from typing import Optional
from openai import OpenAI
from models.core import TimedSegment
from services.providers import SpeechToTextProvider, TranscriptionResult
from utils.provider_errors import ProviderError, map_openai_error


class OpenAISpeechToText(SpeechToTextProvider):
    """OpenAI Whisper语音转文字提供者"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if not self.api_key:
            raise ProviderError("OpenAI API密钥未设置")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "whisper-1"
        self.supported_formats = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']
        self.max_file_size = 25 * 1024 * 1024  # 25MB限制
    
    def transcribe(self, audio_path: str, language: Optional[str] = None, 
                  prompt: Optional[str] = None) -> TranscriptionResult:
        """转录音频文件"""
        if not os.path.exists(audio_path):
            raise ProviderError(f"音频文件不存在: {audio_path}")
        
        self._validate_audio_file(audio_path)
        
        try:
            params = {
                "model": self.model,
                "response_format": "json"
            }
            
            if language:
                params["language"] = language
            
            if prompt:
                params["prompt"] = prompt
            
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    file=audio_file,
                    **params
                )
            
            transcription_text = response.text
            detected_language = getattr(response, 'language', None)
            
            return TranscriptionResult(
                text=transcription_text,
                language=detected_language
            )
            
        except Exception as e:
            raise map_openai_error(type(e).__name__.lower(), str(e))
    
    def transcribe_with_timestamps(self, audio_path: str, language: Optional[str] = None,
                                 prompt: Optional[str] = None) -> TranscriptionResult:
        """转录音频文件并获取时间戳信息"""
        if not os.path.exists(audio_path):
            raise ProviderError(f"音频文件不存在: {audio_path}")
        
        self._validate_audio_file(audio_path)
        
        try:
            params = {
                "model": self.model,
                "response_format": "verbose_json",
                "timestamp_granularities": ["segment"]
            }
            
            if language:
                params["language"] = language
            
            if prompt:
                params["prompt"] = prompt
            
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    file=audio_file,
                    **params
                )
            
            transcription_text = response.text
            detected_language = getattr(response, 'language', None)
            duration = getattr(response, 'duration', None)
            
            # 解析片段
            segments = []
            if hasattr(response, 'segments') and response.segments:
                for i, segment in enumerate(response.segments):
                    timed_segment = TimedSegment(
                        start_time=segment.start,
                        end_time=segment.end,
                        original_text=segment.text.strip(),
                        confidence=getattr(segment, 'avg_logprob', 0.0),
                        speaker_id=f"speaker_{i % 2}"
                    )
                    segments.append(timed_segment)
            
            return TranscriptionResult(
                text=transcription_text,
                language=detected_language,
                duration=duration,
                segments=segments
            )
            
        except Exception as e:
            raise map_openai_error(type(e).__name__.lower(), str(e))
    
    def detect_language(self, audio_path: str) -> str:
        """检测音频语言"""
        if not os.path.exists(audio_path):
            raise ProviderError(f"音频文件不存在: {audio_path}")
        
        try:
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model=self.model,
                    response_format="json"
                )
            
            return getattr(response, 'language', 'unknown')
            
        except Exception as e:
            raise map_openai_error(type(e).__name__.lower(), str(e))
    
    def _validate_audio_file(self, audio_path: str):
        """验证音频文件"""
        # 检查文件格式
        file_ext = os.path.splitext(audio_path)[1].lower()
        if file_ext not in self.supported_formats:
            raise ProviderError(f"不支持的文件格式: {file_ext}")
        
        # 检查文件大小
        file_size = os.path.getsize(audio_path)
        if file_size > self.max_file_size:
            raise ProviderError(f"文件太大: {file_size} bytes (最大 {self.max_file_size} bytes)")