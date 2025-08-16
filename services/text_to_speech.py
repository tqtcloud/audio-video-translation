import os
import time
import tempfile
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import openai
from pydub import AudioSegment
from pydub.utils import which
from models.core import TimedSegment
from config import Config


class TextToSpeechServiceError(Exception):
    """文本转语音服务错误"""
    pass


@dataclass
class SpeechSynthesisResult:
    """语音合成结果"""
    audio_file_path: str
    total_duration: float
    segments_count: int
    processing_time: float
    quality_score: float
    timing_adjustments: List[Tuple[int, float]]  # (segment_index, speed_adjustment)


@dataclass
class VoiceConfig:
    """语音配置"""
    voice_id: str
    language: str
    speed: float = 1.0
    pitch: float = 0.0
    emotion: str = "neutral"
    
    
class TextToSpeechService:
    """
    文本转语音服务
    
    集成 OpenAI TTS API 实现文本到语音的转换功能，
    配置语音参数和质量设置，处理 API 限制和错误恢复。
    实现语音速度调整功能以匹配原始时序，保持情感语调和韵律特征。
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化文本转语音服务
        
        Args:
            api_key: OpenAI API密钥
        """
        self.api_key = api_key or Config.OPENAI_API_KEY
        if not self.api_key:
            raise TextToSpeechServiceError("未提供 OpenAI API 密钥")
        
        # 初始化 OpenAI 客户端
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
            'model': 'tts-1-hd',  # 高质量模型
            'response_format': 'mp3',
            'speed': 1.0
        }
        
        # 时序匹配配置
        self.timing_config = {
            'max_speed_adjustment': 0.3,  # 最大速度调整范围 ±30%
            'min_segment_duration': 0.1,  # 最小片段持续时间
            'silence_padding': 0.05,      # 片段间静音填充
            'timing_tolerance': 0.1       # 时序容差
        }
        
        # API 请求配置
        self.max_retries = 3
        self.retry_delay = 1.0
        self.max_text_length = 4096  # OpenAI TTS 单次请求最大字符数
        
        # 检查 FFmpeg 依赖
        if not which("ffmpeg"):
            raise TextToSpeechServiceError("未找到 FFmpeg，请确保已安装")
    
    def synthesize_speech(self, segments: List[TimedSegment],
                         language: str,
                         voice_config: Optional[VoiceConfig] = None,
                         match_original_timing: bool = True) -> SpeechSynthesisResult:
        """
        合成语音
        
        Args:
            segments: 时序文本片段列表
            language: 目标语言代码
            voice_config: 语音配置
            match_original_timing: 是否匹配原始时序
            
        Returns:
            SpeechSynthesisResult: 语音合成结果
            
        Raises:
            TextToSpeechServiceError: 合成失败
        """
        if not segments:
            raise TextToSpeechServiceError("输入片段列表为空")
        
        if language not in self.voice_mapping:
            raise TextToSpeechServiceError(f"不支持的语言: {language}")
        
        start_time = time.time()
        
        try:
            # 设置默认语音配置
            if not voice_config:
                voice_config = VoiceConfig(
                    voice_id=self.voice_mapping[language]['default'],
                    language=language
                )
            
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
            
            # 计算质量分数
            quality_score = self._calculate_synthesis_quality(
                segments, combined_audio, timing_adjustments
            )
            
            processing_time = time.time() - start_time
            
            return SpeechSynthesisResult(
                audio_file_path=output_path,
                total_duration=len(combined_audio) / 1000.0,
                segments_count=len(segments),
                processing_time=processing_time,
                quality_score=quality_score,
                timing_adjustments=timing_adjustments
            )
            
        except Exception as e:
            raise TextToSpeechServiceError(f"语音合成失败: {str(e)}")
    
    def synthesize_text(self, text: str, 
                       language: str,
                       voice_config: Optional[VoiceConfig] = None) -> str:
        """
        合成单个文本的语音
        
        Args:
            text: 待合成文本
            language: 语言代码
            voice_config: 语音配置
            
        Returns:
            str: 生成的音频文件路径
            
        Raises:
            TextToSpeechServiceError: 合成失败
        """
        if not text.strip():
            raise TextToSpeechServiceError("输入文本为空")
        
        if language not in self.voice_mapping:
            raise TextToSpeechServiceError(f"不支持的语言: {language}")
        
        try:
            # 设置默认语音配置
            if not voice_config:
                voice_config = VoiceConfig(
                    voice_id=self.voice_mapping[language]['default'],
                    language=language
                )
            
            # 调用 TTS API
            audio_data = self._call_tts_api(text, voice_config)
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(audio_data)
                return temp_file.name
                
        except Exception as e:
            raise TextToSpeechServiceError(f"文本语音合成失败: {str(e)}")
    
    def get_supported_voices(self, language: str) -> Dict[str, str]:
        """
        获取支持的语音列表
        
        Args:
            language: 语言代码
            
        Returns:
            Dict[str, str]: 语音类型到语音ID的映射
        """
        if language not in self.voice_mapping:
            return {}
        
        return self.voice_mapping[language].copy()
    
    def adjust_speech_timing(self, audio_file_path: str,
                           target_duration: float,
                           output_path: Optional[str] = None) -> str:
        """
        调整语音时序以匹配目标持续时间
        
        Args:
            audio_file_path: 输入音频文件路径
            target_duration: 目标持续时间（秒）
            output_path: 输出文件路径（可选）
            
        Returns:
            str: 调整后的音频文件路径
            
        Raises:
            TextToSpeechServiceError: 调整失败
        """
        try:
            # 加载音频
            audio = AudioSegment.from_file(audio_file_path)
            current_duration = len(audio) / 1000.0
            
            # 计算速度调整倍率
            speed_ratio = current_duration / target_duration
            
            # 限制速度调整范围
            max_adjustment = self.timing_config['max_speed_adjustment']
            speed_ratio = max(1 - max_adjustment, min(1 + max_adjustment, speed_ratio))
            
            # 调整音频速度
            adjusted_audio = self._adjust_audio_speed(audio, speed_ratio)
            
            # 保存调整后的音频
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            adjusted_audio.export(output_path, format="mp3")
            
            return output_path
            
        except Exception as e:
            raise TextToSpeechServiceError(f"语音时序调整失败: {str(e)}")
    
    def validate_synthesis_quality(self, segments: List[TimedSegment],
                                 audio_file_path: str) -> Dict[str, float]:
        """
        验证语音合成质量
        
        Args:
            segments: 原始文本片段
            audio_file_path: 合成的音频文件路径
            
        Returns:
            Dict[str, float]: 质量指标
        """
        try:
            audio = AudioSegment.from_file(audio_file_path)
            audio_duration = len(audio) / 1000.0
            
            # 计算预期持续时间
            expected_duration = segments[-1].end_time if segments else 0.0
            
            # 时序准确性
            timing_accuracy = 1.0 - min(1.0, abs(audio_duration - expected_duration) / expected_duration) \
                if expected_duration > 0 else 0.0
            
            # 音频质量（基于音量、频率分布等简单指标）
            audio_quality = self._analyze_audio_quality(audio)
            
            # 片段完整性
            completeness = self._check_segment_completeness(segments, audio)
            
            # 综合评分
            overall_score = (timing_accuracy + audio_quality + completeness) / 3
            
            return {
                'timing_accuracy': timing_accuracy,
                'audio_quality': audio_quality,
                'completeness': completeness,
                'overall_score': overall_score
            }
            
        except Exception as e:
            return {
                'timing_accuracy': 0.0,
                'audio_quality': 0.0,
                'completeness': 0.0,
                'overall_score': 0.0
            }
    
    def _synthesize_segment(self, segment: TimedSegment,
                          voice_config: VoiceConfig,
                          match_timing: bool) -> Tuple[AudioSegment, float]:
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
            if target_duration > self.timing_config['min_segment_duration']:
                speed_ratio = current_duration / target_duration
                max_adjustment = self.timing_config['max_speed_adjustment']
                
                if abs(speed_ratio - 1.0) > self.timing_config['timing_tolerance']:
                    speed_ratio = max(1 - max_adjustment, min(1 + max_adjustment, speed_ratio))
                    audio = self._adjust_audio_speed(audio, speed_ratio)
                    speed_adjustment = speed_ratio
        
        return audio, speed_adjustment
    
    def _call_tts_api(self, text: str, voice_config: VoiceConfig) -> bytes:
        """调用 TTS API"""
        # 分块处理长文本
        if len(text) > self.max_text_length:
            chunks = self._split_text_into_chunks(text)
            audio_chunks = []
            
            for chunk in chunks:
                chunk_audio = self._call_tts_api_single(chunk, voice_config)
                audio_chunks.append(chunk_audio)
            
            # 合并音频块
            return self._merge_audio_chunks(audio_chunks)
        else:
            return self._call_tts_api_single(text, voice_config)
    
    def _call_tts_api_single(self, text: str, voice_config: VoiceConfig) -> bytes:
        """调用单次 TTS API"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = openai.audio.speech.create(
                    model=self.quality_settings['model'],
                    voice=voice_config.voice_id,
                    input=text,
                    response_format=self.quality_settings['response_format'],
                    speed=voice_config.speed
                )
                
                return response.content
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                
        raise TextToSpeechServiceError(f"TTS API调用失败，已重试{self.max_retries}次: {str(last_error)}")
    
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
                
                if gap_duration > self.timing_config['silence_padding']:
                    silence_duration = max(0, gap_duration - self.timing_config['silence_padding'])
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
        # 使用 pydub 的速度调整功能
        # speed_ratio > 1 表示加速，< 1 表示减速
        
        # 导出到临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_input:
            audio.export(temp_input.name, format="wav")
            
            # 使用 FFmpeg 调整速度
            with tempfile.NamedTemporaryFile(suffix='.wav') as temp_output:
                os.system(f'ffmpeg -y -i "{temp_input.name}" -filter:a "atempo={speed_ratio}" "{temp_output.name}" 2>/dev/null')
                
                # 加载调整后的音频
                try:
                    adjusted_audio = AudioSegment.from_wav(temp_output.name)
                    return adjusted_audio
                except:
                    # 如果失败，返回原音频
                    return audio
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """将长文本分割为块"""
        if len(text) <= self.max_text_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # 按句号分割，但保留句号
        sentences = []
        parts = text.split('。')  # 使用中文句号
        for i, part in enumerate(parts):
            if part.strip():  # 跳过空部分
                if i < len(parts) - 1:  # 不是最后一部分，加上句号
                    sentences.append(part.strip() + '。')
                else:  # 最后一部分，保持原样
                    sentences.append(part.strip())
        
        for sentence in sentences:
            if not sentence:
                continue
                
            # 测试添加当前句子是否超过限制
            test_chunk = current_chunk + sentence if current_chunk else sentence
            
            if len(test_chunk) <= self.max_text_length:  # 修改为 <=
                current_chunk = test_chunk
            else:
                # 超过限制，保存当前块并开始新块
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _merge_audio_chunks(self, audio_chunks: List[bytes]) -> bytes:
        """合并音频块"""
        audio_segments = []
        
        for chunk_data in audio_chunks:
            with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
                temp_file.write(chunk_data)
                temp_file.flush()
                audio_segment = AudioSegment.from_file(temp_file.name)
                audio_segments.append(audio_segment)
        
        # 合并所有片段
        combined = AudioSegment.empty()
        for segment in audio_segments:
            combined += segment
        
        # 导出为字节
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            combined.export(temp_file.name, format="mp3")
            with open(temp_file.name, 'rb') as f:
                return f.read()
    
    def _calculate_synthesis_quality(self, segments: List[TimedSegment],
                                   audio: AudioSegment,
                                   timing_adjustments: List[Tuple[int, float]]) -> float:
        """计算语音合成质量分数"""
        quality_factors = []
        
        # 时序匹配度
        if segments:
            expected_duration = segments[-1].end_time
            actual_duration = len(audio) / 1000.0
            timing_score = 1.0 - min(1.0, abs(actual_duration - expected_duration) / expected_duration)
            quality_factors.append(timing_score)
        
        # 调整次数惩罚
        adjustment_penalty = len(timing_adjustments) / len(segments) if segments else 0
        adjustment_score = max(0.5, 1.0 - adjustment_penalty * 0.3)
        quality_factors.append(adjustment_score)
        
        # 音频质量
        audio_quality = self._analyze_audio_quality(audio)
        quality_factors.append(audio_quality)
        
        return sum(quality_factors) / len(quality_factors) if quality_factors else 0.0
    
    def _analyze_audio_quality(self, audio: AudioSegment) -> float:
        """分析音频质量"""
        try:
            # 检查音频长度
            if len(audio) < 100:  # 少于100ms
                return 0.2
            
            # 检查音量
            loudness = audio.dBFS
            if loudness < -40:  # 太安静
                return 0.5
            elif loudness > -6:  # 太大声，可能失真
                return 0.7
            
            # 检查采样率
            if audio.frame_rate < 16000:
                return 0.6
            elif audio.frame_rate >= 44100:
                return 0.9
            
            return 0.8  # 默认良好质量
            
        except:
            return 0.5  # 分析失败，中等质量
    
    def _check_segment_completeness(self, segments: List[TimedSegment],
                                  audio: AudioSegment) -> float:
        """检查片段完整性"""
        if not segments:
            return 0.0
        
        # 简单检查：音频时长是否合理
        text_length = sum(len(seg.translated_text) for seg in segments)
        audio_duration = len(audio) / 1000.0
        
        # 估算合理的语音速度（字符/秒）
        if text_length > 0:
            speech_rate = text_length / audio_duration
            # 合理的语音速度范围
            if 5 <= speech_rate <= 25:  # 5-25字符/秒
                return 1.0
            elif 2 <= speech_rate <= 30:
                return 0.8
            else:
                return 0.5
        
        return 0.7  # 默认值