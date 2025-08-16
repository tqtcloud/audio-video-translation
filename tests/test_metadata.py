import tempfile
import os
import pytest
from unittest.mock import patch, MagicMock
from utils.metadata import MetadataExtractor, MetadataExtractionError
from models.core import FileType, AudioProperties, VideoProperties


class TestMetadataExtractor:
    
    def setup_method(self):
        self.extractor = MetadataExtractor()
    
    def test_extract_metadata_nonexistent_file(self):
        """测试提取不存在文件的元数据"""
        with pytest.raises(MetadataExtractionError, match="文件不存在"):
            self.extractor.extract_metadata("/nonexistent/file.mp4")
    
    @patch('utils.metadata.MetadataExtractor._run_ffprobe')
    def test_extract_audio_metadata(self, mock_ffprobe):
        """测试提取音频文件元数据"""
        # 模拟ffprobe输出
        mock_ffprobe_data = {
            "format": {
                "format_name": "mp3",
                "duration": "120.5",
                "size": "5242880"
            },
            "streams": [{
                "codec_type": "audio",
                "codec_name": "mp3",
                "sample_rate": "44100",
                "channels": 2,
                "duration": "120.5",
                "bit_rate": "128000"
            }]
        }
        mock_ffprobe.return_value = mock_ffprobe_data
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(b'fake audio data')
            tmp_path = tmp.name
        
        try:
            metadata = self.extractor.extract_metadata(tmp_path)
            
            assert metadata.file_type == FileType.AUDIO
            assert metadata.format == "mp3"
            assert metadata.duration == 120.5
            assert metadata.size == 5242880
            assert metadata.video_properties is None
            assert metadata.audio_properties is not None
            assert metadata.audio_properties.sample_rate == 44100
            assert metadata.audio_properties.channels == 2
            assert metadata.audio_properties.bitrate == 128000
            
        finally:
            os.unlink(tmp_path)
    
    @patch('utils.metadata.MetadataExtractor._run_ffprobe')
    def test_extract_video_metadata(self, mock_ffprobe):
        """测试提取视频文件元数据"""
        # 模拟ffprobe输出
        mock_ffprobe_data = {
            "format": {
                "format_name": "mp4",
                "duration": "300.0",
                "size": "10485760"
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1"
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                    "duration": "300.0"
                }
            ]
        }
        mock_ffprobe.return_value = mock_ffprobe_data
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp.write(b'fake video data')
            tmp_path = tmp.name
        
        try:
            metadata = self.extractor.extract_metadata(tmp_path)
            
            assert metadata.file_type == FileType.VIDEO
            assert metadata.format == "mp4"
            assert metadata.duration == 300.0
            assert metadata.size == 10485760
            
            # 检查视频属性
            assert metadata.video_properties is not None
            assert metadata.video_properties.width == 1920
            assert metadata.video_properties.height == 1080
            assert metadata.video_properties.fps == 30.0
            assert metadata.video_properties.codec == "h264"
            
            # 检查音频属性
            assert metadata.audio_properties is not None
            assert metadata.audio_properties.sample_rate == 48000
            assert metadata.audio_properties.channels == 2
            
        finally:
            os.unlink(tmp_path)
    
    def test_extract_audio_properties(self):
        """测试提取音频流属性"""
        audio_stream = {
            "sample_rate": "44100",
            "channels": 2,
            "duration": "120.5",
            "bit_rate": "128000"
        }
        
        properties = self.extractor._extract_audio_properties(audio_stream)
        
        assert properties.sample_rate == 44100
        assert properties.channels == 2
        assert properties.duration == 120.5
        assert properties.bitrate == 128000
    
    def test_extract_video_properties(self):
        """测试提取视频流属性"""
        video_stream = {
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
            "codec_name": "h264"
        }
        
        properties = self.extractor._extract_video_properties(video_stream)
        
        assert properties.width == 1920
        assert properties.height == 1080
        assert properties.fps == 30.0
        assert properties.codec == "h264"