import os
import mimetypes
from typing import Tuple, Optional
from pathlib import Path
from config import Config


class ValidationError(Exception):
    """文件验证错误"""
    pass


class FileValidator:
    """文件验证器"""
    
    def __init__(self):
        self.config = Config()
    
    def validate_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        验证文件格式和大小
        
        Args:
            file_path: 文件路径
            
        Returns:
            (is_valid, error_message) 元组
        """
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        # 验证文件大小
        file_size = os.path.getsize(file_path)
        if file_size > self.config.MAX_FILE_SIZE:
            return False, f"文件大小超过限制 ({self.config.MAX_FILE_SIZE // (1024*1024*1024)}GB)"
        
        if file_size == 0:
            return False, "文件为空"
        
        # 验证文件格式
        is_valid_format, format_error = self._validate_format(file_path)
        if not is_valid_format:
            return False, format_error
            
        return True, None
    
    def _validate_format(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """验证文件格式"""
        file_extension = Path(file_path).suffix.lower().lstrip('.')
        
        # 检查是否为支持的视频格式
        if file_extension in self.config.SUPPORTED_VIDEO_FORMATS:
            return self._validate_video_format(file_path)
        
        # 检查是否为支持的音频格式  
        if file_extension in self.config.SUPPORTED_AUDIO_FORMATS:
            return self._validate_audio_format(file_path)
        
        supported_formats = self.config.SUPPORTED_VIDEO_FORMATS + self.config.SUPPORTED_AUDIO_FORMATS
        return False, f"不支持的文件格式。支持的格式：{', '.join(supported_formats)}"
    
    def _validate_video_format(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """验证视频文件格式"""
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('video/'):
            return True, None
        return True, None  # 简化实现，依赖扩展名验证
    
    def _validate_audio_format(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """验证音频文件格式"""
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('audio/'):
            return True, None
        return True, None  # 简化实现，依赖扩展名验证
    
    def get_file_type(self, file_path: str) -> str:
        """获取文件类型（video或audio）"""
        file_extension = Path(file_path).suffix.lower().lstrip('.')
        
        if file_extension in self.config.SUPPORTED_VIDEO_FORMATS:
            return "video"
        elif file_extension in self.config.SUPPORTED_AUDIO_FORMATS:
            return "audio"
        else:
            raise ValidationError(f"不支持的文件格式: {file_extension}")