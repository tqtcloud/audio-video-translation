import os
import time
import tempfile
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from pathlib import Path
from pydub.utils import which
import ffmpeg
from models.core import FileType, FileMetadata


class OutputGeneratorError(Exception):
    """输出生成器错误"""
    pass


@dataclass
class OutputResult:
    """输出生成结果"""
    output_path: str
    original_input_path: str
    output_type: str  # 'audio' or 'video'
    file_size_bytes: int
    processing_time: float
    quality_preserved: bool
    format_info: Dict[str, any]
    metadata: Dict[str, any]


@dataclass
class OutputConfig:
    """输出配置"""
    output_directory: str
    file_naming_pattern: str  # 支持变量：{name}, {timestamp}, {type}
    audio_format: str = "mp3"
    video_format: str = "mp4"
    audio_bitrate: str = "192k"
    video_quality: str = "high"  # high, medium, low
    preserve_metadata: bool = True
    overwrite_existing: bool = False


class OutputGenerator:
    """
    输出文件生成服务
    
    为纯音频输入生成翻译音频文件，
    为视频输入生成包含翻译音频的新视频，
    实现输出路径管理和文件命名。
    """
    
    def __init__(self, config: Optional[OutputConfig] = None):
        """初始化输出生成器"""
        # 默认配置
        self.config = config or OutputConfig(
            output_directory="./output",
            file_naming_pattern="{name}_translated_{timestamp}",
            audio_format="mp3",
            video_format="mp4",
            audio_bitrate="192k",
            video_quality="high",
            preserve_metadata=True,
            overwrite_existing=False
        )
        
        # 支持的格式
        self.supported_audio_formats = ['mp3', 'wav', 'aac', 'flac', 'm4a']
        self.supported_video_formats = ['mp4', 'avi', 'mov', 'mkv', 'webm']
        
        # 质量配置映射
        self.quality_configs = {
            'high': {
                'video_crf': 18,
                'video_preset': 'slow',
                'audio_bitrate': '320k'
            },
            'medium': {
                'video_crf': 23,
                'video_preset': 'medium',
                'audio_bitrate': '192k'
            },
            'low': {
                'video_crf': 28,
                'video_preset': 'fast',
                'audio_bitrate': '128k'
            }
        }
        
        # 文件类型检测配置
        self.video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
        self.audio_extensions = {'.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma'}
        
        # 检查依赖
        if not which("ffmpeg"):
            raise OutputGeneratorError("未找到 FFmpeg，请确保已安装")
        
        # 确保输出目录存在
        self._ensure_output_directory()
    
    def generate_output(self, input_path: str,
                       translated_audio_path: str,
                       output_path: Optional[str] = None) -> OutputResult:
        """
        根据输入类型生成对应的输出文件
        
        Args:
            input_path: 原始输入文件路径（音频或视频）
            translated_audio_path: 翻译后的音频文件路径
            output_path: 自定义输出路径（可选）
            
        Returns:
            OutputResult: 输出生成结果
            
        Raises:
            OutputGeneratorError: 生成失败
        """
        if not os.path.exists(input_path):
            raise OutputGeneratorError(f"输入文件不存在: {input_path}")
        
        if not os.path.exists(translated_audio_path):
            raise OutputGeneratorError(f"翻译音频文件不存在: {translated_audio_path}")
        
        start_time = time.time()
        
        try:
            # 检测输入文件类型
            input_type = self._detect_file_type(input_path)
            
            if input_type == FileType.AUDIO:
                result = self._generate_audio_output(
                    input_path, translated_audio_path, output_path
                )
            elif input_type == FileType.VIDEO:
                result = self._generate_video_output(
                    input_path, translated_audio_path, output_path
                )
            else:
                raise OutputGeneratorError(f"不支持的文件类型: {input_path}")
            
            # 更新处理时间
            result.processing_time = time.time() - start_time
            
            return result
            
        except Exception as e:
            raise OutputGeneratorError(f"输出生成失败: {str(e)}")
    
    def generate_audio_output(self, original_audio_path: str,
                            translated_audio_path: str,
                            output_path: Optional[str] = None) -> OutputResult:
        """
        为纯音频输入生成翻译音频文件
        
        Args:
            original_audio_path: 原始音频文件路径
            translated_audio_path: 翻译后的音频文件路径
            output_path: 输出路径（可选）
            
        Returns:
            OutputResult: 音频输出结果
        """
        return self._generate_audio_output(original_audio_path, translated_audio_path, output_path)
    
    def generate_video_output(self, original_video_path: str,
                            translated_audio_path: str,
                            output_path: Optional[str] = None) -> OutputResult:
        """
        为视频输入生成包含翻译音频的新视频
        
        Args:
            original_video_path: 原始视频文件路径
            translated_audio_path: 翻译后的音频文件路径
            output_path: 输出路径（可选）
            
        Returns:
            OutputResult: 视频输出结果
        """
        return self._generate_video_output(original_video_path, translated_audio_path, output_path)
    
    def set_output_config(self, config: OutputConfig):
        """设置输出配置"""
        self.config = config
        self._ensure_output_directory()
    
    def get_output_path_suggestion(self, input_path: str, file_type: str = None) -> str:
        """
        根据输入文件和配置生成建议的输出路径
        
        Args:
            input_path: 输入文件路径
            file_type: 文件类型（'audio' 或 'video'）
            
        Returns:
            str: 建议的输出文件路径
        """
        return self._generate_output_path(input_path, file_type)
    
    def cleanup_temp_files(self, temp_files: List[str]):
        """清理临时文件"""
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass  # 忽略清理错误
    
    def _detect_file_type(self, file_path: str) -> FileType:
        """检测文件类型"""
        try:
            extension = Path(file_path).suffix.lower()
            
            if extension in self.video_extensions:
                return FileType.VIDEO
            elif extension in self.audio_extensions:
                return FileType.AUDIO
            else:
                # 使用 FFprobe 检测
                probe = ffmpeg.probe(file_path)
                
                has_video = any(stream['codec_type'] == 'video' for stream in probe['streams'])
                has_audio = any(stream['codec_type'] == 'audio' for stream in probe['streams'])
                
                if has_video:
                    return FileType.VIDEO
                elif has_audio:
                    return FileType.AUDIO
                else:
                    return FileType.UNKNOWN
                    
        except Exception:
            return FileType.UNKNOWN
    
    def _generate_audio_output(self, original_audio_path: str,
                             translated_audio_path: str,
                             output_path: Optional[str] = None) -> OutputResult:
        """生成音频输出"""
        try:
            # 生成输出路径
            if not output_path:
                output_path = self._generate_output_path(original_audio_path, "audio")
            
            # 检查是否需要覆盖
            if os.path.exists(output_path) and not self.config.overwrite_existing:
                output_path = self._get_unique_path(output_path)
            
            # 获取质量配置
            quality_config = self.quality_configs[self.config.video_quality]
            
            # 复制或转换翻译音频到目标格式
            if self.config.audio_format.lower() == Path(translated_audio_path).suffix[1:].lower():
                # 格式相同，直接复制并可能调整质量
                self._copy_audio_with_quality(translated_audio_path, output_path, quality_config)
            else:
                # 格式转换
                self._convert_audio_format(translated_audio_path, output_path, quality_config)
            
            # 复制元数据（如果需要）
            if self.config.preserve_metadata:
                self._copy_audio_metadata(original_audio_path, output_path)
            
            # 获取输出文件信息
            file_size = os.path.getsize(output_path)
            format_info = self._get_audio_format_info(output_path)
            metadata = self._extract_audio_metadata(output_path)
            
            return OutputResult(
                output_path=output_path,
                original_input_path=original_audio_path,
                output_type="audio",
                file_size_bytes=file_size,
                processing_time=0.0,  # 在上级方法中设置
                quality_preserved=True,
                format_info=format_info,
                metadata=metadata
            )
            
        except Exception as e:
            raise OutputGeneratorError(f"音频输出生成失败: {str(e)}")
    
    def _generate_video_output(self, original_video_path: str,
                             translated_audio_path: str,
                             output_path: Optional[str] = None) -> OutputResult:
        """生成视频输出"""
        try:
            # 生成输出路径
            if not output_path:
                output_path = self._generate_output_path(original_video_path, "video")
            
            # 检查是否需要覆盖
            if os.path.exists(output_path) and not self.config.overwrite_existing:
                output_path = self._get_unique_path(output_path)
            
            # 获取质量配置
            quality_config = self.quality_configs[self.config.video_quality]
            
            # 使用 FFmpeg 替换音频轨道
            self._replace_video_audio_track(
                original_video_path, translated_audio_path, output_path, quality_config
            )
            
            # 复制元数据（如果需要）
            if self.config.preserve_metadata:
                self._copy_video_metadata(original_video_path, output_path)
            
            # 验证输出质量
            quality_preserved = self._verify_video_output_quality(original_video_path, output_path)
            
            # 获取输出文件信息
            file_size = os.path.getsize(output_path)
            format_info = self._get_video_format_info(output_path)
            metadata = self._extract_video_metadata(output_path)
            
            return OutputResult(
                output_path=output_path,
                original_input_path=original_video_path,
                output_type="video",
                file_size_bytes=file_size,
                processing_time=0.0,  # 在上级方法中设置
                quality_preserved=quality_preserved,
                format_info=format_info,
                metadata=metadata
            )
            
        except Exception as e:
            raise OutputGeneratorError(f"视频输出生成失败: {str(e)}")
    
    def _generate_output_path(self, input_path: str, file_type: str = None) -> str:
        """生成输出文件路径"""
        input_file = Path(input_path)
        timestamp = int(time.time())
        
        # 确定文件类型和扩展名
        if not file_type:
            file_type = "video" if self._detect_file_type(input_path) == FileType.VIDEO else "audio"
        
        extension = self.config.video_format if file_type == "video" else self.config.audio_format
        
        # 生成文件名
        filename = self.config.file_naming_pattern.format(
            name=input_file.stem,
            timestamp=timestamp,
            type=file_type
        )
        
        output_path = Path(self.config.output_directory) / f"{filename}.{extension}"
        return str(output_path)
    
    def _get_unique_path(self, path: str) -> str:
        """获取唯一的文件路径（避免覆盖）"""
        path_obj = Path(path)
        counter = 1
        
        while os.path.exists(path):
            new_name = f"{path_obj.stem}_{counter}{path_obj.suffix}"
            path = str(path_obj.parent / new_name)
            counter += 1
        
        return path
    
    def _ensure_output_directory(self):
        """确保输出目录存在"""
        os.makedirs(self.config.output_directory, exist_ok=True)
    
    def _copy_audio_with_quality(self, input_path: str, output_path: str, quality_config: Dict):
        """复制音频并调整质量"""
        try:
            (
                ffmpeg
                .input(input_path)
                .output(
                    output_path,
                    acodec='mp3' if self.config.audio_format == 'mp3' else 'aac',
                    audio_bitrate=quality_config['audio_bitrate']
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except Exception as e:
            raise OutputGeneratorError(f"音频质量调整失败: {str(e)}")
    
    def _convert_audio_format(self, input_path: str, output_path: str, quality_config: Dict):
        """转换音频格式"""
        try:
            (
                ffmpeg
                .input(input_path)
                .output(
                    output_path,
                    acodec='mp3' if self.config.audio_format == 'mp3' else 'aac',
                    audio_bitrate=quality_config['audio_bitrate'],
                    ar=44100  # 标准采样率
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except Exception as e:
            raise OutputGeneratorError(f"音频格式转换失败: {str(e)}")
    
    def _replace_video_audio_track(self, video_path: str, audio_path: str, 
                                 output_path: str, quality_config: Dict):
        """替换视频音频轨道"""
        try:
            (
                ffmpeg
                .output(
                    ffmpeg.input(video_path).video,
                    ffmpeg.input(audio_path).audio,
                    output_path,
                    vcodec='copy',  # 复制视频流，保持质量
                    acodec='aac',
                    audio_bitrate=quality_config['audio_bitrate']
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except Exception as e:
            raise OutputGeneratorError(f"视频音频轨道替换失败: {str(e)}")
    
    def _copy_audio_metadata(self, source_path: str, target_path: str):
        """复制音频元数据"""
        try:
            # 使用 FFmpeg 复制元数据
            (
                ffmpeg
                .input(target_path)
                .output(
                    target_path + '.tmp',
                    acodec='copy',
                    **{'map_metadata': '0'}
                )
                .overwrite_output()
                .run(quiet=True)
            )
            
            # 替换文件
            os.replace(target_path + '.tmp', target_path)
            
        except Exception:
            # 元数据复制失败不阻止主流程
            pass
    
    def _copy_video_metadata(self, source_path: str, target_path: str):
        """复制视频元数据"""
        try:
            # 使用 FFmpeg 复制元数据
            (
                ffmpeg
                .input(target_path)
                .output(
                    target_path + '.tmp',
                    vcodec='copy',
                    acodec='copy',
                    **{'map_metadata': '0'}
                )
                .overwrite_output()
                .run(quiet=True)
            )
            
            # 替换文件
            os.replace(target_path + '.tmp', target_path)
            
        except Exception:
            # 元数据复制失败不阻止主流程
            pass
    
    def _verify_video_output_quality(self, original_path: str, output_path: str) -> bool:
        """验证视频输出质量"""
        try:
            # 获取原始和输出文件信息
            original_probe = ffmpeg.probe(original_path)
            output_probe = ffmpeg.probe(output_path)
            
            # 获取视频流信息
            original_video = next(s for s in original_probe['streams'] if s['codec_type'] == 'video')
            output_video = next(s for s in output_probe['streams'] if s['codec_type'] == 'video')
            
            # 检查分辨率是否保持
            resolution_preserved = (
                original_video['width'] == output_video['width'] and
                original_video['height'] == output_video['height']
            )
            
            # 检查时长是否合理（允许小幅差异）
            original_duration = float(original_probe['format']['duration'])
            output_duration = float(output_probe['format']['duration'])
            duration_reasonable = abs(original_duration - output_duration) < 1.0
            
            return resolution_preserved and duration_reasonable
            
        except Exception:
            return False
    
    def _get_audio_format_info(self, audio_path: str) -> Dict[str, any]:
        """获取音频格式信息"""
        try:
            probe = ffmpeg.probe(audio_path)
            audio_stream = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
            
            return {
                'codec': audio_stream.get('codec_name', 'unknown'),
                'sample_rate': int(audio_stream.get('sample_rate', 0)),
                'channels': int(audio_stream.get('channels', 0)),
                'bitrate': int(audio_stream.get('bit_rate', 0)) if audio_stream.get('bit_rate') else None,
                'duration': float(probe['format'].get('duration', 0)),
                'format': probe['format'].get('format_name', 'unknown')
            }
        except Exception:
            return {}
    
    def _get_video_format_info(self, video_path: str) -> Dict[str, any]:
        """获取视频格式信息"""
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            audio_stream = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            
            info = {
                'video_codec': video_stream.get('codec_name', 'unknown'),
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                'duration': float(probe['format'].get('duration', 0)),
                'format': probe['format'].get('format_name', 'unknown').split(',')[0]
            }
            
            if audio_stream:
                info.update({
                    'audio_codec': audio_stream.get('codec_name', 'unknown'),
                    'audio_sample_rate': int(audio_stream.get('sample_rate', 0)),
                    'audio_channels': int(audio_stream.get('channels', 0))
                })
            
            return info
        except Exception:
            return {}
    
    def _extract_audio_metadata(self, audio_path: str) -> Dict[str, any]:
        """提取音频元数据"""
        try:
            probe = ffmpeg.probe(audio_path)
            return probe.get('format', {}).get('tags', {})
        except Exception:
            return {}
    
    def _extract_video_metadata(self, video_path: str) -> Dict[str, any]:
        """提取视频元数据"""
        try:
            probe = ffmpeg.probe(video_path)
            return probe.get('format', {}).get('tags', {})
        except Exception:
            return {}