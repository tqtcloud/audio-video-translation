import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock
from services.file_service import FileUploadService, FileUploadError
from models.core import FileMetadata, FileType, AudioProperties


class TestFileUploadService:
    
    def setup_method(self):
        self.service = FileUploadService()
        # 创建临时上传目录
        self.temp_upload_dir = tempfile.mkdtemp()
        self.service.config.UPLOAD_DIR = self.temp_upload_dir
    
    def teardown_method(self):
        # 清理临时目录
        if os.path.exists(self.temp_upload_dir):
            shutil.rmtree(self.temp_upload_dir)
    
    def test_upload_file_unsupported_language(self):
        """测试上传文件时指定不支持的语言"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(b'fake audio data')
            tmp_path = tmp.name
        
        try:
            with pytest.raises(FileUploadError, match="不支持的目标语言"):
                self.service.upload_file(tmp_path, "unsupported_lang")
        finally:
            os.unlink(tmp_path)
    
    @patch('services.file_service.FileUploadService.extract_metadata')
    def test_upload_file_validation_failure(self, mock_extract):
        """测试文件验证失败"""
        # 创建一个不支持的文件格式
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b'text content')
            tmp_path = tmp.name
        
        try:
            with pytest.raises(FileUploadError, match="不支持的文件格式"):
                self.service.upload_file(tmp_path, "en")
        finally:
            os.unlink(tmp_path)
    
    @patch('services.file_service.FileUploadService.extract_metadata')
    def test_upload_file_success(self, mock_extract):
        """测试成功上传文件"""
        # 模拟元数据提取
        mock_metadata = FileMetadata(
            file_type=FileType.AUDIO,
            format="mp3",
            duration=120.0,
            size=1024,
            audio_properties=AudioProperties(
                sample_rate=44100,
                channels=2,
                duration=120.0
            )
        )
        mock_extract.return_value = mock_metadata
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(b'fake audio data')
            tmp_path = tmp.name
        
        try:
            uploaded_path, metadata = self.service.upload_file(tmp_path, "en")
            
            # 验证文件被复制到上传目录
            assert uploaded_path.startswith(self.temp_upload_dir)
            assert os.path.exists(uploaded_path)
            
            # 验证元数据
            assert metadata == mock_metadata
            
        finally:
            os.unlink(tmp_path)
    
    def test_validate_file(self):
        """测试文件验证功能"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(b'fake audio data')
            tmp_path = tmp.name
        
        try:
            is_valid, error = self.service.validate_file(tmp_path)
            assert is_valid
            assert error is None
        finally:
            os.unlink(tmp_path)
    
    def test_copy_to_upload_dir_file_exists(self):
        """测试复制文件到上传目录时文件已存在的情况"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(b'fake audio data')
            tmp_path = tmp.name
            filename = os.path.basename(tmp_path)
        
        try:
            # 在上传目录创建同名文件
            existing_file = os.path.join(self.temp_upload_dir, filename)
            with open(existing_file, 'w') as f:
                f.write('existing content')
            
            # 复制文件
            uploaded_path = self.service._copy_to_upload_dir(tmp_path)
            
            # 验证文件名被修改（添加了序号）
            assert uploaded_path != existing_file
            assert uploaded_path.endswith('_1.mp3')
            assert os.path.exists(uploaded_path)
            
        finally:
            os.unlink(tmp_path)