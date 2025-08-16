import os
import time
import tempfile
from typing import List, Dict, Optional, Any
import openai
from pydub import AudioSegment
from models.core import TimedSegment
from services.providers import TextToSpeechProvider, SpeechSynthesisResult
from utils.provider_errors import ProviderError, map_openai_error


class OpenAITextToSpeech(TextToSpeechProvider):
    """OpenAI TTS文字转语音提供者"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if not self.api_key:
            raise ProviderError("OpenAI API密钥未设置")
        
        openai.api_key = self.api_key
        
        # 支持的语音映射
        self.voice_mapping = {
            'en': {
                'male': 'onyx',
                'female': 'nova',
                'default': 'alloy'
            },
            'zh': {
                'male': 'onyx',
                'female': 'nova', 
                'default': 'alloy'
            },
            'es': {
                'male': 'onyx',
                'female': 'nova',
                'default': 'alloy'
            },
            'fr': {
                'male': 'onyx',
                'female': 'nova',
                'default': 'alloy'
            },
            'de': {
                'male': 'onyx',
                'female': 'nova',
                'default': 'alloy'
            }
        }
        
        # 语音质量配置
        self.quality_settings = {
            'model': 'tts-1-hd',
            'response_format': 'mp3',
            'speed': 1.0
        }
        
        # API 请求配置
        self.max_retries = 3
        self.retry_delay = 1.0
        self.max_text_length = 4096
    
    def synthesize_speech(self, segments: List[TimedSegment], language: str,
                         voice_config: Optional[Dict[str, Any]] = None,
                         match_original_timing: bool = True) -> SpeechSynthesisResult:
        """合成语音"""
        if not segments:
            raise ProviderError("输入片段列表为空")
        
        if language not in self.voice_mapping:
            raise ProviderError(f"不支持的语言: {language}")
        
        start_time = time.time()
        
        try:
            # 设置默认语音配置
            if not voice_config:
                voice_config = {
                    'voice_id': self.voice_mapping[language]['default'],
                    'speed': 1.0
                }
            
            # 生成语音片段
            audio_segments = []
            timing_adjustments = []
            
            for i, segment in enumerate(segments):
                if not segment.translated_text.strip():
                    # 跳过空文本，添加静音
                    duration = segment.end_time - segment.start_time
                    silence = AudioSegment.silent(duration=int(duration * 1000))
                    audio_segments.append(silence)
                    continue
                
                # 合成单个片段
                audio_data, speed_adjustment = self._synthesize_segment(
                    segment, voice_config, match_original_timing
                )
                
                audio_segments.append(audio_data)
                
                if speed_adjustment != 1.0:
                    timing_adjustments.append((i, speed_adjustment))
            
            # 合并音频片段
            combined_audio = self._combine_audio_segments(audio_segments, segments)
            
            # 保存到临时文件
            output_path = self._save_audio_file(combined_audio)
            
            processing_time = time.time() - start_time
            
            return SpeechSynthesisResult(
                audio_file_path=output_path,
                total_duration=len(combined_audio) / 1000.0,
                segments_count=len(segments),
                processing_time=processing_time,
                quality_score=0.8,  # 默认质量分数
                timing_adjustments=timing_adjustments
            )
            
        except Exception as e:
            raise map_openai_error(type(e).__name__.lower(), str(e))
    
    def synthesize_text(self, text: str, language: str,
                       voice_config: Optional[Dict[str, Any]] = None) -> str:
        """合成单个文本的语音"""
        if not text.strip():
            raise ProviderError("输入文本为空")
        
        if language not in self.voice_mapping:
            raise ProviderError(f"不支持的语言: {language}")
        
        try:
            # 设置默认语音配置
            if not voice_config:
                voice_config = {
                    'voice_id': self.voice_mapping[language]['default'],
                    'speed': 1.0
                }
            
            # 调用 TTS API
            audio_data = self._call_tts_api(text, voice_config)
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(audio_data)
                return temp_file.name
                
        except Exception as e:
            raise map_openai_error(type(e).__name__.lower(), str(e))
    
    def _synthesize_segment(self, segment: TimedSegment, voice_config: Dict[str, Any],
                          match_timing: bool) -> tuple:
        """合成单个片段"""
        text = segment.translated_text.strip()
        
        # 调用 TTS API
        audio_data = self._call_tts_api(text, voice_config)
        
        # 转换为 AudioSegment
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(audio_data)
            temp_file.flush()
            audio = AudioSegment.from_file(temp_file.name)
        
        speed_adjustment = 1.0
        
        if match_timing:
            # 计算目标持续时间
            target_duration = segment.end_time - segment.start_time
            current_duration = len(audio) / 1000.0
            
            # 调整速度以匹配时序
            if target_duration > 0.1:  # 最小片段持续时间
                speed_ratio = current_duration / target_duration
                
                if abs(speed_ratio - 1.0) > 0.1:  # 时序容差
                    # 限制速度调整范围 ±30%
                    speed_ratio = max(0.7, min(1.3, speed_ratio))
                    audio = self._adjust_audio_speed(audio, speed_ratio)
                    speed_adjustment = speed_ratio
        
        return audio, speed_adjustment
    
    def _call_tts_api(self, text: str, voice_config: Dict[str, Any]) -> bytes:
        """调用 TTS API"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = openai.audio.speech.create(
                    model=self.quality_settings['model'],
                    voice=voice_config.get('voice_id', 'alloy'),
                    input=text,
                    response_format=self.quality_settings['response_format'],
                    speed=voice_config.get('speed', 1.0)
                )
                
                return response.content
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                
        raise map_openai_error(type(last_error).__name__.lower(), str(last_error))
    
    def _combine_audio_segments(self, audio_segments: List[AudioSegment],
                              segments: List[TimedSegment]) -> AudioSegment:
        """合并音频片段"""
        if not audio_segments:
            return AudioSegment.silent(duration=1000)  # 1秒静音
        
        combined = AudioSegment.empty()
        
        for i, (audio, segment) in enumerate(zip(audio_segments, segments)):
            # 添加当前音频片段
            combined += audio
            
            # 添加片段间的静音（如果需要）
            if i < len(segments) - 1:
                next_segment = segments[i + 1]
                gap_duration = next_segment.start_time - segment.end_time
                
                if gap_duration > 0.05:  # 静音填充阈值
                    silence_duration = max(0, gap_duration - 0.05)
                    silence = AudioSegment.silent(duration=int(silence_duration * 1000))
                    combined += silence
        
        return combined
    
    def _save_audio_file(self, audio: AudioSegment) -> str:
        """保存音频文件"""
        output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
        audio.export(output_path, format="mp3", bitrate="128k")
        return output_path
    
    def _adjust_audio_speed(self, audio: AudioSegment, speed_ratio: float) -> AudioSegment:
        """调整音频速度"""
        try:
            # 导出到临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav') as temp_input:
                audio.export(temp_input.name, format="wav")
                
                # 使用 FFmpeg 调整速度
                with tempfile.NamedTemporaryFile(suffix='.wav') as temp_output:
                    os.system(f'ffmpeg -y -i "{temp_input.name}" -filter:a "atempo={speed_ratio}" "{temp_output.name}" 2>/dev/null')
                    
                    # 加载调整后的音频
                    adjusted_audio = AudioSegment.from_wav(temp_output.name)
                    return adjusted_audio
        except:
            # 如果失败，返回原音频
            return audio