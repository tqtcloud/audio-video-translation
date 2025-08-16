import os
import ffmpeg
import json
from typing import Optional, Dict, Any
from models.core import AudioProperties, FileType


class AudioExtractionError(Exception):
    """音频提取错误"""
    pass


class AudioExtractor:
    """
    音频提取器
    
    使用 FFmpeg 从视频文件中提取高质量音频，
    获取音频属性信息，保留时序信息和元数据。
    """
    
    def __init__(self):
        self.default_audio_params = {
            'acodec': 'pcm_s16le',  # 16位PCM编码
            'ar': 44100,            # 44.1kHz采样率
            'ac': 1                 # 单声道（用于语音识别）
        }
    
    def extract_audio(self, input_path: str, output_path: Optional[str] = None, 
                     high_quality: bool = True) -> str:
        """
        从视频或音频文件中提取音频
        
        Args:
            input_path: 输入文件路径
            output_path: 输出音频文件路径（可选）
            high_quality: 是否使用高质量参数
            
        Returns:
            提取的音频文件路径
            
        Raises:
            AudioExtractionError: 音频提取失败
        """
        if not os.path.exists(input_path):
            raise AudioExtractionError(f"输入文件不存在: {input_path}")
        
        # 生成输出路径
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.dirname(input_path)
            output_path = os.path.join(output_dir, f"{base_name}_extracted.wav")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            # 设置音频参数
            audio_params = self.default_audio_params.copy()
            if high_quality:
                audio_params.update({
                    'ar': 48000,        # 48kHz采样率用于高质量
                    'ac': 2             # 立体声保留更多信息
                })
            
            # 使用FFmpeg提取音频
            (
                ffmpeg
                .input(input_path)
                .output(output_path, **audio_params)
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
            
            if not os.path.exists(output_path):
                raise AudioExtractionError("音频提取失败：输出文件未生成")
            
            return output_path
            
        except Exception as e:
            if hasattr(e, 'stderr') and e.stderr:
                error_msg = f"FFmpeg错误: {e.stderr.decode() if hasattr(e.stderr, 'decode') else str(e.stderr)}"
            else:
                error_msg = f"音频提取失败: {str(e)}"
            raise AudioExtractionError(error_msg)
    
    def get_audio_properties(self, file_path: str) -> AudioProperties:
        """
        获取音频文件的属性信息
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            AudioProperties: 音频属性对象
            
        Raises:
            AudioExtractionError: 获取属性失败
        """
        if not os.path.exists(file_path):
            raise AudioExtractionError(f"文件不存在: {file_path}")
        
        try:
            # 使用ffprobe获取音频信息
            probe = ffmpeg.probe(file_path, v='quiet', print_format='json', show_streams=True)
            
            # 查找音频流
            audio_stream = None
            for stream in probe.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    audio_stream = stream
                    break
            
            if not audio_stream:
                raise AudioExtractionError("未找到音频流")
            
            # 提取音频属性
            sample_rate = int(audio_stream.get('sample_rate', 0))
            channels = int(audio_stream.get('channels', 0))
            duration = float(audio_stream.get('duration', 0))
            bitrate = int(audio_stream.get('bit_rate', 0)) if audio_stream.get('bit_rate') else None
            
            return AudioProperties(
                sample_rate=sample_rate,
                channels=channels,
                duration=duration,
                bitrate=bitrate
            )
            
        except Exception as e:
            if hasattr(e, 'stderr') and e.stderr:
                error_msg = f"FFprobe错误: {e.stderr.decode() if hasattr(e.stderr, 'decode') else str(e.stderr)}"
            else:
                error_msg = f"获取音频属性失败: {str(e)}"
            raise AudioExtractionError(error_msg)
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        获取文件的完整元数据信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含详细元数据的字典
            
        Raises:
            AudioExtractionError: 获取元数据失败
        """
        if not os.path.exists(file_path):
            raise AudioExtractionError(f"文件不存在: {file_path}")
        
        try:
            # 获取完整的文件信息
            probe = ffmpeg.probe(file_path, v='quiet', print_format='json', 
                               show_format=True, show_streams=True)
            
            format_info = probe.get('format', {})
            streams = probe.get('streams', [])
            
            # 分析文件类型
            file_type = FileType.AUDIO
            video_streams = [s for s in streams if s.get('codec_type') == 'video']
            if video_streams:
                file_type = FileType.VIDEO
            
            # 提取基本信息
            metadata = {
                'file_type': file_type,
                'format_name': format_info.get('format_name', ''),
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else None,
                'streams_count': len(streams),
                'audio_streams': [],
                'video_streams': [],
                'tags': format_info.get('tags', {})
            }
            
            # 处理音频流
            for stream in streams:
                if stream.get('codec_type') == 'audio':
                    audio_info = {
                        'index': stream.get('index'),
                        'codec_name': stream.get('codec_name'),
                        'sample_rate': int(stream.get('sample_rate', 0)),
                        'channels': int(stream.get('channels', 0)),
                        'duration': float(stream.get('duration', 0)),
                        'bitrate': int(stream.get('bit_rate', 0)) if stream.get('bit_rate') else None
                    }
                    metadata['audio_streams'].append(audio_info)
            
            # 处理视频流
            for stream in streams:
                if stream.get('codec_type') == 'video':
                    video_info = {
                        'index': stream.get('index'),
                        'codec_name': stream.get('codec_name'),
                        'width': int(stream.get('width', 0)),
                        'height': int(stream.get('height', 0)),
                        'fps': self._parse_fps(stream.get('r_frame_rate', '0/1')),
                        'duration': float(stream.get('duration', 0))
                    }
                    metadata['video_streams'].append(video_info)
            
            return metadata
            
        except Exception as e:
            if hasattr(e, 'stderr') and e.stderr:
                error_msg = f"FFprobe错误: {e.stderr.decode() if hasattr(e.stderr, 'decode') else str(e.stderr)}"
            else:
                error_msg = f"获取文件元数据失败: {str(e)}"
            raise AudioExtractionError(error_msg)
    
    def extract_audio_segment(self, input_path: str, output_path: str, 
                            start_time: float, duration: float) -> str:
        """
        提取音频片段（保留时序信息）
        
        Args:
            input_path: 输入文件路径
            output_path: 输出音频文件路径
            start_time: 开始时间（秒）
            duration: 持续时间（秒）
            
        Returns:
            提取的音频片段文件路径
            
        Raises:
            AudioExtractionError: 音频片段提取失败
        """
        if not os.path.exists(input_path):
            raise AudioExtractionError(f"输入文件不存在: {input_path}")
        
        if start_time < 0 or duration <= 0:
            raise AudioExtractionError("无效的时间参数")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            # 使用FFmpeg提取音频片段
            (
                ffmpeg
                .input(input_path, ss=start_time, t=duration)
                .output(output_path, **self.default_audio_params)
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
            
            if not os.path.exists(output_path):
                raise AudioExtractionError("音频片段提取失败：输出文件未生成")
            
            return output_path
            
        except Exception as e:
            if hasattr(e, 'stderr') and e.stderr:
                error_msg = f"FFmpeg错误: {e.stderr.decode() if hasattr(e.stderr, 'decode') else str(e.stderr)}"
            else:
                error_msg = f"音频片段提取失败: {str(e)}"
            raise AudioExtractionError(error_msg)
    
    def normalize_audio(self, input_path: str, output_path: str, 
                       target_db: float = -20.0) -> str:
        """
        音频标准化处理
        
        Args:
            input_path: 输入音频文件路径
            output_path: 输出音频文件路径
            target_db: 目标音量（dB）
            
        Returns:
            标准化后的音频文件路径
            
        Raises:
            AudioExtractionError: 音频标准化失败
        """
        if not os.path.exists(input_path):
            raise AudioExtractionError(f"输入文件不存在: {input_path}")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            # 使用FFmpeg进行音频标准化
            (
                ffmpeg
                .input(input_path)
                .filter('loudnorm', I=target_db)
                .output(output_path, **self.default_audio_params)
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
            
            if not os.path.exists(output_path):
                raise AudioExtractionError("音频标准化失败：输出文件未生成")
            
            return output_path
            
        except Exception as e:
            if hasattr(e, 'stderr') and e.stderr:
                error_msg = f"FFmpeg错误: {e.stderr.decode() if hasattr(e.stderr, 'decode') else str(e.stderr)}"
            else:
                error_msg = f"音频标准化失败: {str(e)}"
            raise AudioExtractionError(error_msg)
    
    def _parse_fps(self, fps_string: str) -> float:
        """解析帧率字符串"""
        try:
            if '/' in fps_string:
                num, den = fps_string.split('/')
                return float(num) / float(den) if float(den) != 0 else 0.0
            return float(fps_string)
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    def check_ffmpeg_available(self) -> bool:
        """检查FFmpeg是否可用"""
        try:
            ffmpeg.probe('dummy', v='quiet')
            return True
        except:
            return False