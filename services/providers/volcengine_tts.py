import json
import time
import uuid
import tempfile
import requests
from typing import List, Dict, Optional, Any
from pydub import AudioSegment
from models.core import TimedSegment
from services.providers import TextToSpeechProvider, SpeechSynthesisResult
from models.adapters import VolcengineTTSAdapter
from utils.provider_errors import ProviderError, map_volcengine_error


class VolcengineTextToSpeech(TextToSpeechProvider):
    """火山云语音合成提供者"""
    
    def __init__(self, app_id: str, access_token: str):
        if not app_id or not access_token:
            raise ProviderError("火山云TTS配置参数不完整")
        
        self.app_id = app_id
        self.access_token = access_token
        self.base_url = "https://openspeech.bytedance.com/api/v1/tts"
        
        # 请求配置
        self.max_retries = 3
        self.retry_delay = 1.0
        self.request_timeout = 30
        self.max_text_length = 1000  # 火山云单次请求限制
        
        # 音频配置
        self.default_encoding = "mp3"
        self.default_sample_rate = 24000
    
    def synthesize_speech(self, segments: List[TimedSegment], language: str,
                         voice_config: Optional[Dict[str, Any]] = None,
                         match_original_timing: bool = True) -> SpeechSynthesisResult:
        """合成语音"""
        if not segments:
            raise ProviderError("输入片段列表为空")
        
        start_time = time.time()
        
        try:
            # 获取语音配置
            voice_mapping = VolcengineTTSAdapter.adapt_voice_mapping(language)
            if not voice_mapping:
                raise ProviderError(f"不支持的语言: {language}")
            
            if not voice_config:
                voice_config = {'voice_id': voice_mapping['default']}
            
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
                    segment, language, voice_config, match_original_timing
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
                quality_score=0.85,  # 火山云质量分数
                timing_adjustments=timing_adjustments
            )
            
        except Exception as e:
            if isinstance(e, ProviderError):
                raise e
            raise ProviderError(f"火山云TTS合成失败: {str(e)}")
    
    def synthesize_text(self, text: str, language: str,
                       voice_config: Optional[Dict[str, Any]] = None) -> str:
        """合成单个文本的语音"""
        if not text.strip():
            raise ProviderError("输入文本为空")
        
        try:
            # 获取语音配置
            voice_mapping = VolcengineTTSAdapter.adapt_voice_mapping(language)
            if not voice_mapping:
                raise ProviderError(f"不支持的语言: {language}")
            
            if not voice_config:
                voice_config = {'voice_id': voice_mapping['default']}
            
            # 调用TTS API
            audio_data = self._call_tts_api(text, language, voice_config)
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(audio_data)
                return temp_file.name
                
        except Exception as e:
            if isinstance(e, ProviderError):
                raise e
            raise ProviderError(f"火山云TTS文本合成失败: {str(e)}")
    
    def _synthesize_segment(self, segment: TimedSegment, language: str,
                          voice_config: Dict[str, Any], match_timing: bool) -> tuple:
        """合成单个片段"""
        text = segment.translated_text.strip()
        
        # 调用TTS API
        audio_data = self._call_tts_api(text, language, voice_config)
        
        # 转换为AudioSegment
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
    
    def _call_tts_api(self, text: str, language: str, voice_config: Dict[str, Any]) -> bytes:
        """调用火山云TTS API"""
        # 分块处理长文本
        if len(text) > self.max_text_length:
            chunks = self._split_text_into_chunks(text)
            audio_chunks = []
            
            for chunk in chunks:
                chunk_audio = self._call_tts_api_single(chunk, language, voice_config)
                audio_chunks.append(chunk_audio)
            
            return self._merge_audio_chunks(audio_chunks)
        else:
            return self._call_tts_api_single(text, language, voice_config)
    
    def _call_tts_api_single(self, text: str, language: str, voice_config: Dict[str, Any]) -> bytes:
        """调用单次TTS API"""
        # 构建请求数据
        request_data = VolcengineTTSAdapter.adapt_request([], language, voice_config)
        request_data["app"]["appid"] = self.app_id
        request_data["app"]["token"] = self.access_token
        request_data["request"]["reqid"] = str(uuid.uuid4())
        request_data["request"]["text"] = text
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=request_data,
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get("message") == "success":
                        # 获取音频数据
                        audio_data = result.get("data", {}).get("audio")
                        if audio_data:
                            import base64
                            return base64.b64decode(audio_data)
                        else:
                            raise ProviderError("火山云TTS响应中缺少音频数据")
                    else:
                        error_code = result.get("code", "unknown")
                        error_msg = result.get("message", "未知错误")
                        raise map_volcengine_error(str(error_code), error_msg)
                else:
                    raise ProviderError(f"火山云TTS API请求失败: HTTP {response.status_code}")
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        
        if isinstance(last_error, ProviderError):
            raise last_error
        raise ProviderError(f"火山云TTS API调用失败，已重试{self.max_retries}次: {str(last_error)}")
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """将长文本分割为块"""
        if len(text) <= self.max_text_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # 按句号分割
        sentences = []
        parts = text.split('。')
        for i, part in enumerate(parts):
            if part.strip():
                if i < len(parts) - 1:
                    sentences.append(part.strip() + '。')
                else:
                    sentences.append(part.strip())
        
        for sentence in sentences:
            if not sentence:
                continue
                
            test_chunk = current_chunk + sentence if current_chunk else sentence
            
            if len(test_chunk) <= self.max_text_length:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
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
    
    def _combine_audio_segments(self, audio_segments: List[AudioSegment],
                              segments: List[TimedSegment]) -> AudioSegment:
        """合并音频片段"""
        if not audio_segments:
            return AudioSegment.silent(duration=1000)
        
        combined = AudioSegment.empty()
        
        for i, (audio, segment) in enumerate(zip(audio_segments, segments)):
            combined += audio
            
            # 添加片段间的静音
            if i < len(segments) - 1:
                next_segment = segments[i + 1]
                gap_duration = next_segment.start_time - segment.end_time
                
                if gap_duration > 0.05:
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
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.wav') as temp_input:
                audio.export(temp_input.name, format="wav")
                
                with tempfile.NamedTemporaryFile(suffix='.wav') as temp_output:
                    os.system(f'ffmpeg -y -i "{temp_input.name}" -filter:a "atempo={speed_ratio}" "{temp_output.name}" 2>/dev/null')
                    
                    try:
                        adjusted_audio = AudioSegment.from_wav(temp_output.name)
                        return adjusted_audio
                    except:
                        return audio
        except:
            return audio