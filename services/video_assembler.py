import os
import time
import tempfile
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pydub.utils import which
import ffmpeg
from models.core import FileType, FileMetadata


class VideoAssemblerError(Exception):
    """视频组装器错误"""
    pass


@dataclass
class AudioReplacementResult:
    """音频替换结果"""
    output_video_path: str
    original_video_info: Dict[str, any]
    replacement_audio_info: Dict[str, any]
    processing_time: float
    quality_preserved: bool
    format_compatibility: bool


@dataclass
class VideoInfo:
    """视频信息"""
    width: int
    height: int
    fps: float
    duration: float
    codec: str
    bitrate: Optional[int] = None
    format: str = "mp4"


class VideoAssembler:
    """
    视频组装和音频轨道替换服务
    
    使用 FFmpeg 实现视频中音频轨道的替换，
    保持原始视频质量和分辨率，处理不同视频格式的兼容性。
    """
    
    def __init__(self):
        """初始化视频组装器"""
        # 支持的视频格式
        self.supported_video_formats = ['mp4', 'avi', 'mov', 'mkv', 'webm', 'flv']
        self.supported_audio_formats = ['mp3', 'wav', 'aac', 'flac', 'm4a']
        
        # 视频质量配置
        self.video_config = {
            'preserve_quality': True,      # 保持原始质量
            'copy_video_stream': True,     # 复制视频流（不重新编码）
            'default_video_codec': 'libx264',  # 默认视频编解码器
            'default_audio_codec': 'aac',  # 默认音频编解码器
            'quality_preset': 'medium',    # 质量预设
            'max_bitrate_ratio': 1.5       # 最大比特率倍数
        }
        
        # 兼容性配置
        self.compatibility_config = {
            'auto_format_conversion': True,  # 自动格式转换
            'force_keyframe_alignment': True,  # 强制关键帧对齐
            'audio_sync_offset': 0.0,      # 音频同步偏移
            'fallback_formats': ['mp4', 'mov']  # 回退格式
        }
        
        # 检查依赖
        if not which("ffmpeg"):
            raise VideoAssemblerError("未找到 FFmpeg，请确保已安装")
    
    def replace_audio_track(self, video_path: str,
                          new_audio_path: str,
                          output_path: Optional[str] = None,
                          preserve_quality: bool = True) -> AudioReplacementResult:
        """
        替换视频中的音频轨道
        
        Args:
            video_path: 输入视频文件路径
            new_audio_path: 新音频文件路径
            output_path: 输出视频文件路径（可选）
            preserve_quality: 是否保持原始视频质量
            
        Returns:
            AudioReplacementResult: 音频替换结果
            
        Raises:
            VideoAssemblerError: 替换失败
        """
        if not os.path.exists(video_path):
            raise VideoAssemblerError(f"视频文件不存在: {video_path}")
        
        if not os.path.exists(new_audio_path):
            raise VideoAssemblerError(f"音频文件不存在: {new_audio_path}")
        
        start_time = time.time()
        
        try:
            # 分析输入文件信息
            video_info = self._get_video_info(video_path)
            audio_info = self._get_audio_info(new_audio_path)
            
            # 验证格式兼容性
            format_compatible = self._check_format_compatibility(video_path, new_audio_path)
            
            # 生成输出路径
            if not output_path:
                video_ext = os.path.splitext(video_path)[1]
                output_path = tempfile.NamedTemporaryFile(suffix=video_ext, delete=False).name
            
            # 执行音频替换
            if preserve_quality:
                self._replace_audio_with_quality_preservation(
                    video_path, new_audio_path, output_path, video_info
                )
            else:
                self._replace_audio_simple(
                    video_path, new_audio_path, output_path
                )
            
            # 验证输出质量
            quality_preserved = self._verify_output_quality(
                video_path, output_path, video_info
            )
            
            processing_time = time.time() - start_time
            
            return AudioReplacementResult(
                output_video_path=output_path,
                original_video_info=video_info.__dict__,
                replacement_audio_info=audio_info,
                processing_time=processing_time,
                quality_preserved=quality_preserved,
                format_compatibility=format_compatible
            )
            
        except Exception as e:
            raise VideoAssemblerError(f"音频轨道替换失败: {str(e)}")
    
    def extract_video_stream(self, video_path: str,
                           output_path: Optional[str] = None) -> str:
        """
        提取视频流（无音频）
        
        Args:
            video_path: 输入视频文件路径
            output_path: 输出文件路径（可选）
            
        Returns:
            str: 提取的视频文件路径
            
        Raises:
            VideoAssemblerError: 提取失败
        """
        if not os.path.exists(video_path):
            raise VideoAssemblerError(f"视频文件不存在: {video_path}")
        
        try:
            # 生成输出路径
            if not output_path:
                video_ext = os.path.splitext(video_path)[1]
                output_path = tempfile.NamedTemporaryFile(suffix=video_ext, delete=False).name
            
            # 使用 FFmpeg 提取视频流
            (
                ffmpeg
                .input(video_path)
                .video  # 只选择视频流
                .output(output_path, vcodec='copy')  # 复制视频编码
                .overwrite_output()
                .run(quiet=True)
            )
            
            return output_path
            
        except Exception as e:
            raise VideoAssemblerError(f"视频流提取失败: {str(e)}")
    
    def merge_video_audio(self, video_path: str,
                         audio_path: str,
                         output_path: Optional[str] = None,
                         sync_offset: float = 0.0) -> str:
        """
        合并视频和音频流
        
        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            output_path: 输出文件路径（可选）
            sync_offset: 音频同步偏移（秒）
            
        Returns:
            str: 合并后的视频文件路径
            
        Raises:
            VideoAssemblerError: 合并失败
        """
        if not os.path.exists(video_path):
            raise VideoAssemblerError(f"视频文件不存在: {video_path}")
        
        if not os.path.exists(audio_path):
            raise VideoAssemblerError(f"音频文件不存在: {audio_path}")
        
        try:
            # 生成输出路径
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name
            
            # 构建 FFmpeg 命令
            video_input = ffmpeg.input(video_path)
            audio_input = ffmpeg.input(audio_path)
            
            # 应用音频偏移
            if sync_offset != 0.0:
                audio_input = audio_input.filter('adelay', f'{int(sync_offset * 1000)}|{int(sync_offset * 1000)}')
            
            # 合并视频和音频
            (
                ffmpeg
                .output(video_input.video, audio_input.audio, output_path,
                       vcodec='copy', acodec='aac', audio_bitrate='192k')
                .overwrite_output()
                .run(quiet=True)
            )
            
            return output_path
            
        except Exception as e:
            raise VideoAssemblerError(f"视频音频合并失败: {str(e)}")
    
    def convert_video_format(self, video_path: str,
                           target_format: str,
                           output_path: Optional[str] = None,
                           preserve_quality: bool = True) -> str:
        """
        转换视频格式
        
        Args:
            video_path: 输入视频文件路径
            target_format: 目标格式（如 'mp4', 'mov'）
            output_path: 输出文件路径（可选）
            preserve_quality: 是否保持质量
            
        Returns:
            str: 转换后的视频文件路径
            
        Raises:
            VideoAssemblerError: 转换失败
        """
        if not os.path.exists(video_path):
            raise VideoAssemblerError(f"视频文件不存在: {video_path}")
        
        if target_format not in self.supported_video_formats:
            raise VideoAssemblerError(f"不支持的目标格式: {target_format}")
        
        try:
            # 生成输出路径
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix=f'.{target_format}', delete=False).name
            
            # 构建转换参数
            if preserve_quality:
                # 高质量转换
                (
                    ffmpeg
                    .input(video_path)
                    .output(output_path, 
                           vcodec=self.video_config['default_video_codec'],
                           acodec=self.video_config['default_audio_codec'],
                           preset=self.video_config['quality_preset'],
                           crf=18)  # 高质量CRF值
                    .overwrite_output()
                    .run(quiet=True)
                )
            else:
                # 快速转换
                (
                    ffmpeg
                    .input(video_path)
                    .output(output_path,
                           vcodec='copy' if self._can_copy_codec(video_path, target_format) else self.video_config['default_video_codec'],
                           acodec='copy')
                    .overwrite_output()
                    .run(quiet=True)
                )
            
            return output_path
            
        except Exception as e:
            raise VideoAssemblerError(f"视频格式转换失败: {str(e)}")
    
    def get_video_metadata(self, video_path: str) -> Dict[str, any]:
        """
        获取视频元数据
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Dict[str, any]: 视频元数据
            
        Raises:
            VideoAssemblerError: 获取失败
        """
        if not os.path.exists(video_path):
            raise VideoAssemblerError(f"视频文件不存在: {video_path}")
        
        try:
            # 使用 FFprobe 获取详细信息
            probe = ffmpeg.probe(video_path)
            
            video_stream = None
            audio_stream = None
            
            # 查找视频和音频流
            for stream in probe['streams']:
                if stream['codec_type'] == 'video' and video_stream is None:
                    video_stream = stream
                elif stream['codec_type'] == 'audio' and audio_stream is None:
                    audio_stream = stream
            
            metadata = {
                'format': probe['format'],
                'duration': float(probe['format']['duration']),
                'size': int(probe['format']['size']),
                'bitrate': int(probe['format']['bit_rate']) if 'bit_rate' in probe['format'] else None,
                'video_stream': video_stream,
                'audio_stream': audio_stream
            }
            
            return metadata
            
        except Exception as e:
            raise VideoAssemblerError(f"视频元数据获取失败: {str(e)}")
    
    def _get_video_info(self, video_path: str) -> VideoInfo:
        """获取视频信息"""
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next(stream for stream in probe['streams'] 
                              if stream['codec_type'] == 'video')
            
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            fps = eval(video_stream['r_frame_rate'])  # 如 '30/1' -> 30.0
            duration = float(probe['format']['duration'])
            codec = video_stream['codec_name']
            bitrate = int(video_stream.get('bit_rate', 0)) if video_stream.get('bit_rate') else None
            format_name = probe['format']['format_name'].split(',')[0]
            
            return VideoInfo(
                width=width,
                height=height,
                fps=fps,
                duration=duration,
                codec=codec,
                bitrate=bitrate,
                format=format_name
            )
            
        except Exception as e:
            raise VideoAssemblerError(f"获取视频信息失败: {str(e)}")
    
    def _get_audio_info(self, audio_path: str) -> Dict[str, any]:
        """获取音频信息"""
        try:
            probe = ffmpeg.probe(audio_path)
            audio_stream = next(stream for stream in probe['streams'] 
                              if stream['codec_type'] == 'audio')
            
            return {
                'codec': audio_stream['codec_name'],
                'sample_rate': int(audio_stream['sample_rate']),
                'channels': int(audio_stream['channels']),
                'duration': float(probe['format']['duration']),
                'bitrate': int(audio_stream.get('bit_rate', 0)) if audio_stream.get('bit_rate') else None
            }
            
        except Exception as e:
            raise VideoAssemblerError(f"获取音频信息失败: {str(e)}")
    
    def _check_format_compatibility(self, video_path: str, audio_path: str) -> bool:
        """检查格式兼容性"""
        try:
            video_ext = os.path.splitext(video_path)[1][1:].lower()
            audio_ext = os.path.splitext(audio_path)[1][1:].lower()
            
            # 检查是否为支持的格式
            video_supported = video_ext in self.supported_video_formats
            audio_supported = audio_ext in self.supported_audio_formats
            
            return video_supported and audio_supported
            
        except:
            return False
    
    def _replace_audio_with_quality_preservation(self, video_path: str,
                                               audio_path: str,
                                               output_path: str,
                                               video_info: VideoInfo):
        """保持质量的音频替换"""
        try:
            # 使用复制视频流的方式，避免重新编码
            video_input = ffmpeg.input(video_path)
            audio_input = ffmpeg.input(audio_path)
            
            # 构建输出参数
            output_kwargs = {
                'vcodec': 'copy',  # 复制视频编码，保持原始质量
                'acodec': 'aac',   # 音频使用AAC编码
                'audio_bitrate': '192k'
            }
            
            # 如果原视频时长和新音频时长不匹配，需要处理
            if abs(video_info.duration - self._get_audio_duration(audio_path)) > 0.1:
                # 调整音频长度以匹配视频
                audio_input = audio_input.filter('apad')  # 填充或截断
            
            (
                ffmpeg
                .output(video_input.video, audio_input.audio, output_path, **output_kwargs)
                .overwrite_output()
                .run(quiet=True)
            )
            
        except Exception as e:
            raise VideoAssemblerError(f"高质量音频替换失败: {str(e)}")
    
    def _replace_audio_simple(self, video_path: str, audio_path: str, output_path: str):
        """简单音频替换"""
        try:
            (
                ffmpeg
                .output(
                    ffmpeg.input(video_path).video,
                    ffmpeg.input(audio_path).audio,
                    output_path,
                    vcodec='copy',
                    acodec='aac'
                )
                .overwrite_output()
                .run(quiet=True)
            )
            
        except Exception as e:
            raise VideoAssemblerError(f"简单音频替换失败: {str(e)}")
    
    def _verify_output_quality(self, original_path: str, output_path: str,
                             original_info: VideoInfo) -> bool:
        """验证输出质量"""
        try:
            # 获取输出视频信息
            output_info = self._get_video_info(output_path)
            
            # 检查分辨率是否保持
            resolution_preserved = (
                output_info.width == original_info.width and
                output_info.height == original_info.height
            )
            
            # 检查帧率是否保持（允许小幅差异）
            fps_preserved = abs(output_info.fps - original_info.fps) < 0.1
            
            # 检查时长是否合理（允许小幅差异）
            duration_reasonable = abs(output_info.duration - original_info.duration) < 1.0
            
            return resolution_preserved and fps_preserved and duration_reasonable
            
        except:
            return False
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            probe = ffmpeg.probe(audio_path)
            return float(probe['format']['duration'])
        except:
            return 0.0
    
    def _can_copy_codec(self, video_path: str, target_format: str) -> bool:
        """检查是否可以复制编解码器"""
        try:
            video_info = self._get_video_info(video_path)
            
            # 简单的兼容性检查
            compatible_codecs = {
                'mp4': ['h264', 'h265', 'mpeg4'],
                'mov': ['h264', 'h265', 'prores'],
                'avi': ['h264', 'mpeg4', 'xvid'],
                'mkv': ['h264', 'h265', 'vp8', 'vp9']
            }
            
            return (target_format in compatible_codecs and 
                    video_info.codec in compatible_codecs[target_format])
            
        except:
            return False