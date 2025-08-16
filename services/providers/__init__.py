from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from models.core import TimedSegment


class TranscriptionResult:
    """转录结果"""
    
    def __init__(self, text: str, language: Optional[str] = None, 
                 duration: Optional[float] = None, segments: Optional[List[TimedSegment]] = None):
        self.text = text
        self.language = language
        self.duration = duration
        self.segments = segments or []


class SpeechSynthesisResult:
    """语音合成结果"""
    
    def __init__(self, audio_file_path: str, total_duration: float, 
                 segments_count: int, processing_time: float, quality_score: float,
                 timing_adjustments: List[tuple] = None):
        self.audio_file_path = audio_file_path
        self.total_duration = total_duration
        self.segments_count = segments_count
        self.processing_time = processing_time
        self.quality_score = quality_score
        self.timing_adjustments = timing_adjustments or []


class TranslationResult:
    """翻译结果"""
    
    def __init__(self, original_segments: List[TimedSegment], translated_segments: List[TimedSegment],
                 total_characters: int, processing_time: float, language_detected: str, quality_score: float):
        self.original_segments = original_segments
        self.translated_segments = translated_segments
        self.total_characters = total_characters
        self.processing_time = processing_time
        self.language_detected = language_detected
        self.quality_score = quality_score


class SpeechToTextProvider(ABC):
    """语音转文字提供者抽象基类"""
    
    @abstractmethod
    def transcribe(self, audio_path: str, language: Optional[str] = None, 
                  prompt: Optional[str] = None) -> TranscriptionResult:
        """转录音频文件"""
        pass
    
    @abstractmethod
    def transcribe_with_timestamps(self, audio_path: str, language: Optional[str] = None,
                                 prompt: Optional[str] = None) -> TranscriptionResult:
        """转录音频文件并获取时间戳信息"""
        pass
    
    @abstractmethod
    def detect_language(self, audio_path: str) -> str:
        """检测音频语言"""
        pass


class TextToSpeechProvider(ABC):
    """文字转语音提供者抽象基类"""
    
    @abstractmethod
    def synthesize_speech(self, segments: List[TimedSegment], language: str,
                         voice_config: Optional[Dict[str, Any]] = None,
                         match_original_timing: bool = True) -> SpeechSynthesisResult:
        """合成语音"""
        pass
    
    @abstractmethod
    def synthesize_text(self, text: str, language: str,
                       voice_config: Optional[Dict[str, Any]] = None) -> str:
        """合成单个文本的语音"""
        pass


class TranslationProvider(ABC):
    """翻译提供者抽象基类"""
    
    @abstractmethod
    def translate_segments(self, segments: List[TimedSegment], 
                          target_language: str,
                          source_language: Optional[str] = None) -> TranslationResult:
        """翻译时序片段"""
        pass
    
    @abstractmethod
    def translate_text(self, text: str, target_language: str,
                      source_language: Optional[str] = None) -> str:
        """翻译单个文本"""
        pass