import os
import tempfile
import pytest
from utils.validation import FileValidator, ValidationError


class TestFileValidator:
    
    def setup_method(self):
        self.validator = FileValidator()
    
    def test_validate_nonexistent_file(self):
        """测试验证不存在的文件"""
        is_valid, error = self.validator.validate_file("/nonexistent/file.mp4")
        assert not is_valid
        assert "文件不存在" in error
    
    def test_validate_empty_file(self):
        """测试验证空文件"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            is_valid, error = self.validator.validate_file(tmp_path)
            assert not is_valid
            assert "文件为空" in error
        finally:
            os.unlink(tmp_path)
    
    def test_validate_large_file(self):
        """测试验证超大文件"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            # 写入一些数据但不超过实际限制（为了测试速度）
            tmp.write(b'x' * 1024)  # 1KB
            tmp_path = tmp.name
        
        try:
            # 临时修改配置中的文件大小限制进行测试
            original_size = self.validator.config.MAX_FILE_SIZE
            self.validator.config.MAX_FILE_SIZE = 512  # 512 bytes
            
            is_valid, error = self.validator.validate_file(tmp_path)
            assert not is_valid
            assert "文件大小超过限制" in error
            
            # 恢复原始配置
            self.validator.config.MAX_FILE_SIZE = original_size
        finally:
            os.unlink(tmp_path)
    
    def test_validate_supported_video_format(self):
        """测试验证支持的视频格式"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp.write(b'fake video data')
            tmp_path = tmp.name
        
        try:
            is_valid, error = self.validator.validate_file(tmp_path)
            assert is_valid
            assert error is None
        finally:
            os.unlink(tmp_path)
    
    def test_validate_supported_audio_format(self):
        """测试验证支持的音频格式"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(b'fake audio data')
            tmp_path = tmp.name
        
        try:
            is_valid, error = self.validator.validate_file(tmp_path)
            assert is_valid
            assert error is None
        finally:
            os.unlink(tmp_path)
    
    def test_validate_unsupported_format(self):
        """测试验证不支持的格式"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b'text content')
            tmp_path = tmp.name
        
        try:
            is_valid, error = self.validator.validate_file(tmp_path)
            assert not is_valid
            assert "不支持的文件格式" in error
        finally:
            os.unlink(tmp_path)
    
    def test_get_file_type_video(self):
        """测试获取视频文件类型"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            file_type = self.validator.get_file_type(tmp_path)
            assert file_type == "video"
        finally:
            os.unlink(tmp_path)
    
    def test_get_file_type_audio(self):
        """测试获取音频文件类型"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            file_type = self.validator.get_file_type(tmp_path)
            assert file_type == "audio"
        finally:
            os.unlink(tmp_path)
    
    def test_get_file_type_unsupported(self):
        """测试获取不支持文件的类型"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with pytest.raises(ValidationError, match="不支持的文件格式"):
                self.validator.get_file_type(tmp_path)
        finally:
            os.unlink(tmp_path)