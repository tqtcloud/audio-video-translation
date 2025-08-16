import os
import time
from typing import List, Optional, Dict, Any
from models.core import TimedSegment
from config import Config
from services.provider_factory import provider_manager
from services.providers import TranscriptionResult
from utils.provider_errors import ProviderError


class SpeechToTextError(Exception):
    """语音转文本错误"""
    pass


class SpeechToTextService:
    """
    语音转文本服务
    
    支持多提供者的音频转录服务，可以使用 OpenAI Whisper 或火山云ASR，
    支持多语言识别、时序数据提取和说话人识别。
    """
    
    def __init__(self, provider_type: Optional[str] = None):
        """
        初始化语音转文字服务
        
        Args:
            provider_type: 指定提供者类型，如果为None则使用配置中的默认值
        """
        self.config = Config()
        
        # 如果指定了提供者类型，临时设置配置
        if provider_type:
            original_provider = self.config.STT_PROVIDER
            self.config.STT_PROVIDER = provider_type
        
        try:
            self.provider = provider_manager.get_stt_provider()
        except ProviderError as e:
            raise SpeechToTextError(f"初始化语音转文字提供者失败: {str(e)}")
        finally:
            # 恢复原始配置
            if provider_type:
                self.config.STT_PROVIDER = original_provider
    
    def transcribe(self, audio_path: str, language: Optional[str] = None, 
                  prompt: Optional[str] = None) -> TranscriptionResult:
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 指定语言代码（可选）
            prompt: 提示文本，帮助模型理解上下文（可选）
            
        Returns:
            TranscriptionResult: 转录结果
            
        Raises:
            SpeechToTextError: 转录失败
        """
        try:
            return self.provider.transcribe(audio_path, language, prompt)
        except ProviderError as e:
            raise SpeechToTextError(f"转录失败: {str(e)}")
        except Exception as e:
            raise SpeechToTextError(f"转录失败: {str(e)}")
    
    def transcribe_with_timestamps(self, audio_path: str, language: Optional[str] = None,
                                 prompt: Optional[str] = None) -> TranscriptionResult:
        """
        转录音频文件并获取时间戳信息
        
        Args:
            audio_path: 音频文件路径
            language: 指定语言代码（可选）
            prompt: 提示文本（可选）
            
        Returns:
            TranscriptionResult: 包含时间戳的转录结果
            
        Raises:
            SpeechToTextError: 转录失败
        """
        try:
            return self.provider.transcribe_with_timestamps(audio_path, language, prompt)
        except ProviderError as e:
            raise SpeechToTextError(f"时间戳转录失败: {str(e)}")
        except Exception as e:
            raise SpeechToTextError(f"时间戳转录失败: {str(e)}")
    
    def get_timing_data(self, audio_path: str, language: Optional[str] = None) -> List[TimedSegment]:
        """
        获取音频的详细时序数据
        
        Args:
            audio_path: 音频文件路径
            language: 指定语言代码（可选）
            
        Returns:
            List[TimedSegment]: 时序片段列表
            
        Raises:
            SpeechToTextError: 获取时序数据失败
        """
        result = self.transcribe_with_timestamps(audio_path, language)
        return result.segments
    
    def detect_language(self, audio_path: str) -> str:
        """
        检测音频语言
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            str: 检测到的语言代码
            
        Raises:
            SpeechToTextError: 语言检测失败
        """
        if not os.path.exists(audio_path):
            raise SpeechToTextError(f"音频文件不存在: {audio_path}")
        
        try:
            return self.provider.detect_language(audio_path)
        except ProviderError as e:
            raise SpeechToTextError(f"语言检测失败: {str(e)}")
        except Exception as e:
            raise SpeechToTextError(f"语言检测失败: {str(e)}")
    
    def validate_api_key(self) -> bool:
        """
        验证API密钥是否有效
        
        Returns:
            bool: API密钥是否有效
        """
        try:
            return self.provider.validate_api_key()
        except Exception:
            return False
    
    def get_supported_languages(self) -> List[str]:
        """
        获取支持的语言列表
        
        Returns:
            List[str]: 支持的语言代码列表
        """
        try:
            return self.provider.get_supported_languages()
        except Exception:
            # 如果提供者没有实现，返回默认列表
            return [
                'en',  # English
                'zh',  # Chinese
                'es',  # Spanish
                'fr',  # French
                'de',  # German
                'ja',  # Japanese
                'ko',  # Korean
                'pt',  # Portuguese
                'ru',  # Russian
                'it',  # Italian
                'ar',  # Arabic
                'hi',  # Hindi
            ]
    
    def split_long_audio(self, audio_path: str, max_duration: float = 600.0) -> List[str]:
        """
        分割长音频文件以符合API限制
        
        Args:
            audio_path: 音频文件路径
            max_duration: 最大持续时间（秒）
            
        Returns:
            List[str]: 分割后的音频文件路径列表
            
        Raises:
            SpeechToTextError: 分割失败
        """
        if not os.path.exists(audio_path):
            raise SpeechToTextError(f"音频文件不存在: {audio_path}")
        
        try:
            # 委托给提供者处理（如果支持）
            if hasattr(self.provider, 'split_long_audio'):
                return self.provider.split_long_audio(audio_path, max_duration)
            
            # 默认实现：简单检查文件大小
            file_size = os.path.getsize(audio_path)
            max_file_size = 25 * 1024 * 1024  # 25MB默认限制
            
            if file_size <= max_file_size:
                return [audio_path]
            else:
                raise SpeechToTextError("音频文件太大，需要分割处理")
                
        except ProviderError as e:
            raise SpeechToTextError(f"分割音频失败: {str(e)}")
        except Exception as e:
            raise SpeechToTextError(f"分割音频失败: {str(e)}")
    
    def transcribe_large_file(self, audio_path: str, language: Optional[str] = None) -> TranscriptionResult:
        """
        转录大文件（自动分割处理）
        
        Args:
            audio_path: 音频文件路径
            language: 指定语言代码（可选）
            
        Returns:
            TranscriptionResult: 合并的转录结果
            
        Raises:
            SpeechToTextError: 转录失败
        """
        try:
            # 分割文件
            audio_chunks = self.split_long_audio(audio_path)
            
            # 转录每个片段
            all_segments = []
            all_text = []
            total_duration = 0.0
            detected_language = None
            
            for chunk_path in audio_chunks:
                result = self.transcribe_with_timestamps(chunk_path, language)
                
                # 调整时间偏移
                for segment in result.segments:
                    segment.start_time += total_duration
                    segment.end_time += total_duration
                    all_segments.append(segment)
                
                all_text.append(result.text)
                
                if result.duration:
                    total_duration += result.duration
                
                if not detected_language and result.language:
                    detected_language = result.language
            
            # 合并结果
            combined_text = " ".join(all_text)
            
            return TranscriptionResult(
                text=combined_text,
                language=detected_language,
                duration=total_duration,
                segments=all_segments
            )
            
        except Exception as e:
            raise SpeechToTextError(f"大文件转录失败: {str(e)}")
    
    def enhance_transcription_quality(self, audio_path: str, context: Optional[str] = None) -> TranscriptionResult:
        """
        增强转录质量（使用上下文提示）
        
        Args:
            audio_path: 音频文件路径
            context: 上下文信息，帮助改善转录质量
            
        Returns:
            TranscriptionResult: 转录结果
            
        Raises:
            SpeechToTextError: 转录失败
        """
        # 构建智能提示
        prompt = ""
        if context:
            prompt = f"Context: {context}. "
        
        # 添加一些通用的质量改善提示
        prompt += "Please transcribe accurately with proper punctuation and capitalization."
        
        return self.transcribe_with_timestamps(audio_path, prompt=prompt)