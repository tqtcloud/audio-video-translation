import os
import shutil
from typing import Tuple, Optional
from pathlib import Path
from utils.validation import FileValidator, ValidationError
from utils.metadata import MetadataExtractor, MetadataExtractionError
from models.core import FileMetadata
from config import Config


class FileUploadError(Exception):
    """文件上传错误"""
    pass


class FileUploadService:
    """文件上传服务"""
    
    def __init__(self):
        self.validator = FileValidator()
        self.metadata_extractor = MetadataExtractor()
        self.config = Config()
        
        # 确保上传目录存在
        os.makedirs(self.config.UPLOAD_DIR, exist_ok=True)
    
    def upload_file(self, file_path: str, target_language: str) -> Tuple[str, FileMetadata]:
        """
        上传文件并验证
        
        Args:
            file_path: 源文件路径
            target_language: 目标语言
            
        Returns:
            (uploaded_file_path, file_metadata) 元组
            
        Raises:
            FileUploadError: 文件上传或验证失败
        """
        try:
            # 验证目标语言
            if target_language not in self.config.SUPPORTED_LANGUAGES:
                raise FileUploadError(f"不支持的目标语言: {target_language}")
            
            # 验证文件
            is_valid, error_msg = self.validator.validate_file(file_path)
            if not is_valid:
                raise FileUploadError(error_msg)
            
            # 复制文件到上传目录
            uploaded_path = self._copy_to_upload_dir(file_path)
            
            # 提取元数据
            metadata = self.extract_metadata(uploaded_path)
            
            return uploaded_path, metadata
            
        except (ValidationError, MetadataExtractionError) as e:
            raise FileUploadError(str(e))
    
    def validate_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """验证文件"""
        return self.validator.validate_file(file_path)
    
    def extract_metadata(self, file_path: str) -> FileMetadata:
        """提取文件元数据"""
        return self.metadata_extractor.extract_metadata(file_path)
    
    def _copy_to_upload_dir(self, source_path: str) -> str:
        """将文件复制到上传目录"""
        source_file = Path(source_path)
        destination = Path(self.config.UPLOAD_DIR) / source_file.name
        
        # 如果目标文件已存在，添加序号
        counter = 1
        while destination.exists():
            stem = source_file.stem
            suffix = source_file.suffix
            destination = Path(self.config.UPLOAD_DIR) / f"{stem}_{counter}{suffix}"
            counter += 1
        
        try:
            shutil.copy2(source_path, destination)
            return str(destination)
        except Exception as e:
            raise FileUploadError(f"文件复制失败: {str(e)}")