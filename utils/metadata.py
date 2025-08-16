import json
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path
from models.core import FileMetadata, FileType, AudioProperties, VideoProperties


class MetadataExtractionError(Exception):
    """元数据提取错误"""
    pass


class MetadataExtractor:
    """使用FFprobe提取文件元数据"""
    
    def extract_metadata(self, file_path: str) -> FileMetadata:
        """
        提取文件元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            FileMetadata对象
        """
        if not Path(file_path).exists():
            raise MetadataExtractionError(f"文件不存在: {file_path}")
        
        try:
            # 使用ffprobe获取文件信息
            probe_data = self._run_ffprobe(file_path)
            
            # 解析元数据
            return self._parse_metadata(file_path, probe_data)
            
        except Exception as e:
            raise MetadataExtractionError(f"元数据提取失败: {str(e)}")
    
    def _run_ffprobe(self, file_path: str) -> Dict[str, Any]:
        """运行ffprobe命令"""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise MetadataExtractionError(f"FFprobe执行失败: {e.stderr}")
        except json.JSONDecodeError as e:
            raise MetadataExtractionError(f"FFprobe输出解析失败: {str(e)}")
    
    def _parse_metadata(self, file_path: str, probe_data: Dict[str, Any]) -> FileMetadata:
        """解析ffprobe输出的元数据"""
        format_info = probe_data.get('format', {})
        streams = probe_data.get('streams', [])
        
        # 基础信息
        file_size = int(format_info.get('size', 0))
        duration = float(format_info.get('duration', 0.0))
        format_name = format_info.get('format_name', '')
        
        # 查找音频和视频流
        video_stream = None
        audio_stream = None
        
        for stream in streams:
            codec_type = stream.get('codec_type')
            if codec_type == 'video' and not video_stream:
                video_stream = stream
            elif codec_type == 'audio' and not audio_stream:
                audio_stream = stream
        
        # 构建音频属性
        audio_properties = self._extract_audio_properties(audio_stream) if audio_stream else None
        
        # 构建视频属性  
        video_properties = self._extract_video_properties(video_stream) if video_stream else None
        
        # 确定文件类型
        file_type = FileType.VIDEO if video_properties else FileType.AUDIO
        
        # 如果是音频文件但没有音频流，从格式信息获取基础音频属性
        if file_type == FileType.AUDIO and not audio_properties:
            audio_properties = AudioProperties(
                sample_rate=44100,  # 默认值
                channels=2,         # 默认值
                duration=duration
            )
        
        return FileMetadata(
            file_type=file_type,
            format=Path(file_path).suffix.lower().lstrip('.'),
            duration=duration,
            size=file_size,
            video_properties=video_properties,
            audio_properties=audio_properties
        )
    
    def _extract_audio_properties(self, audio_stream: Dict[str, Any]) -> AudioProperties:
        """提取音频流属性"""
        sample_rate = int(audio_stream.get('sample_rate', 44100))
        channels = int(audio_stream.get('channels', 2))
        duration = float(audio_stream.get('duration', 0.0))
        bit_rate = audio_stream.get('bit_rate')
        
        return AudioProperties(
            sample_rate=sample_rate,
            channels=channels,
            duration=duration,
            bitrate=int(bit_rate) if bit_rate else None
        )
    
    def _extract_video_properties(self, video_stream: Dict[str, Any]) -> VideoProperties:
        """提取视频流属性"""
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        
        # 计算帧率
        r_frame_rate = video_stream.get('r_frame_rate', '0/1')
        try:
            if '/' in r_frame_rate:
                num, den = map(int, r_frame_rate.split('/'))
                fps = num / den if den != 0 else 0.0
            else:
                fps = float(r_frame_rate)
        except:
            fps = 0.0
        
        codec = video_stream.get('codec_name', 'unknown')
        
        return VideoProperties(
            width=width,
            height=height,
            fps=fps,
            codec=codec
        )