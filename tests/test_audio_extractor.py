import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock
from services.audio_extractor import AudioExtractor, AudioExtractionError
from models.core import AudioProperties, FileType


class TestAudioExtractor:
    
    def setup_method(self):
        self.extractor = AudioExtractor()
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建模拟的输入文件路径
        self.mock_input_path = os.path.join(self.temp_dir, "test_input.mp4")
        self.mock_output_path = os.path.join(self.temp_dir, "test_output.wav")
        
        # 创建模拟输入文件
        with open(self.mock_input_path, 'w') as f:
            f.write("mock file content")
    
    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_default_audio_params(self):
        """测试默认音频参数"""
        expected_params = {
            'acodec': 'pcm_s16le',
            'ar': 44100,
            'ac': 1
        }
        assert self.extractor.default_audio_params == expected_params
    
    @patch('services.audio_extractor.ffmpeg')
    def test_extract_audio_success(self, mock_ffmpeg):
        """测试音频提取成功"""
        # 模拟ffmpeg调用
        mock_input = MagicMock()
        mock_output = MagicMock()
        mock_run = MagicMock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_run
        mock_run.run.return_value = None
        
        # 模拟输出文件生成
        with patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == self.mock_input_path or path == self.mock_output_path
            
            result = self.extractor.extract_audio(self.mock_input_path, self.mock_output_path)
            
            assert result == self.mock_output_path
            mock_ffmpeg.input.assert_called_once_with(self.mock_input_path)
    
    @patch('services.audio_extractor.ffmpeg')
    def test_extract_audio_high_quality(self, mock_ffmpeg):
        """测试高质量音频提取"""
        mock_input = MagicMock()
        mock_output = MagicMock()
        mock_run = MagicMock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_run
        mock_run.run.return_value = None
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == self.mock_input_path or path == self.mock_output_path
            
            self.extractor.extract_audio(self.mock_input_path, self.mock_output_path, high_quality=True)
            
            # 验证高质量参数被使用
            call_args = mock_input.output.call_args
            audio_params = call_args[1]
            assert audio_params['ar'] == 48000  # 高质量采样率
            assert audio_params['ac'] == 2      # 立体声
    
    def test_extract_audio_input_not_exists(self):
        """测试输入文件不存在"""
        non_existent_path = "/path/to/nonexistent/file.mp4"
        
        with pytest.raises(AudioExtractionError, match="输入文件不存在"):
            self.extractor.extract_audio(non_existent_path)
    
    @patch('services.audio_extractor.ffmpeg')
    def test_extract_audio_auto_output_path(self, mock_ffmpeg):
        """测试自动生成输出路径"""
        mock_input = MagicMock()
        mock_output = MagicMock()
        mock_run = MagicMock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_run
        mock_run.run.return_value = None
        
        expected_output = os.path.join(self.temp_dir, "test_input_extracted.wav")
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == self.mock_input_path or path == expected_output
            
            result = self.extractor.extract_audio(self.mock_input_path)
            
            assert result == expected_output
    
    @patch('services.audio_extractor.ffmpeg')
    def test_extract_audio_ffmpeg_error(self, mock_ffmpeg):
        """测试FFmpeg错误处理"""
        # 创建一个模拟的FFmpeg Error
        class MockFFmpegError(Exception):
            def __init__(self, cmd, stdout, stderr):
                self.cmd = cmd
                self.stdout = stdout
                self.stderr = stderr
        
        mock_ffmpeg.Error = MockFFmpegError
        mock_error = MockFFmpegError('test_command', b'stdout', b'stderr_content')
        mock_ffmpeg.input.side_effect = mock_error
        
        with pytest.raises(AudioExtractionError, match="FFmpeg错误"):
            self.extractor.extract_audio(self.mock_input_path)
    
    @patch('services.audio_extractor.ffmpeg')
    def test_get_audio_properties_success(self, mock_ffmpeg):
        """测试获取音频属性成功"""
        # 模拟ffprobe返回数据
        mock_probe_data = {
            'streams': [
                {
                    'codec_type': 'audio',
                    'sample_rate': '44100',
                    'channels': '2',
                    'duration': '120.5',
                    'bit_rate': '128000'
                }
            ]
        }
        
        mock_ffmpeg.probe.return_value = mock_probe_data
        
        properties = self.extractor.get_audio_properties(self.mock_input_path)
        
        assert isinstance(properties, AudioProperties)
        assert properties.sample_rate == 44100
        assert properties.channels == 2
        assert properties.duration == 120.5
        assert properties.bitrate == 128000
    
    @patch('services.audio_extractor.ffmpeg')
    def test_get_audio_properties_no_audio_stream(self, mock_ffmpeg):
        """测试没有音频流的情况"""
        mock_probe_data = {
            'streams': [
                {
                    'codec_type': 'video',
                    'width': 1920,
                    'height': 1080
                }
            ]
        }
        
        mock_ffmpeg.probe.return_value = mock_probe_data
        
        with pytest.raises(AudioExtractionError, match="未找到音频流"):
            self.extractor.get_audio_properties(self.mock_input_path)
    
    def test_get_audio_properties_file_not_exists(self):
        """测试文件不存在"""
        non_existent_path = "/path/to/nonexistent/file.mp3"
        
        with pytest.raises(AudioExtractionError, match="文件不存在"):
            self.extractor.get_audio_properties(non_existent_path)
    
    @patch('services.audio_extractor.ffmpeg')
    def test_get_file_metadata_audio_file(self, mock_ffmpeg):
        """测试获取音频文件元数据"""
        mock_probe_data = {
            'format': {
                'format_name': 'mp3',
                'duration': '180.5',
                'size': '5242880',
                'bit_rate': '128000',
                'tags': {'title': 'Test Audio', 'artist': 'Test Artist'}
            },
            'streams': [
                {
                    'index': 0,
                    'codec_type': 'audio',
                    'codec_name': 'mp3',
                    'sample_rate': '44100',
                    'channels': '2',
                    'duration': '180.5',
                    'bit_rate': '128000'
                }
            ]
        }
        
        mock_ffmpeg.probe.return_value = mock_probe_data
        
        metadata = self.extractor.get_file_metadata(self.mock_input_path)
        
        assert metadata['file_type'] == FileType.AUDIO
        assert metadata['format_name'] == 'mp3'
        assert metadata['duration'] == 180.5
        assert metadata['size'] == 5242880
        assert len(metadata['audio_streams']) == 1
        assert len(metadata['video_streams']) == 0
        assert metadata['tags']['title'] == 'Test Audio'
    
    @patch('services.audio_extractor.ffmpeg')
    def test_get_file_metadata_video_file(self, mock_ffmpeg):
        """测试获取视频文件元数据"""
        mock_probe_data = {
            'format': {
                'format_name': 'mp4',
                'duration': '300.0',
                'size': '52428800'
            },
            'streams': [
                {
                    'index': 0,
                    'codec_type': 'video',
                    'codec_name': 'h264',
                    'width': '1920',
                    'height': '1080',
                    'r_frame_rate': '30/1',
                    'duration': '300.0'
                },
                {
                    'index': 1,
                    'codec_type': 'audio',
                    'codec_name': 'aac',
                    'sample_rate': '48000',
                    'channels': '2',
                    'duration': '300.0'
                }
            ]
        }
        
        mock_ffmpeg.probe.return_value = mock_probe_data
        
        metadata = self.extractor.get_file_metadata(self.mock_input_path)
        
        assert metadata['file_type'] == FileType.VIDEO
        assert metadata['format_name'] == 'mp4'
        assert len(metadata['audio_streams']) == 1
        assert len(metadata['video_streams']) == 1
        assert metadata['video_streams'][0]['width'] == 1920
        assert metadata['video_streams'][0]['height'] == 1080
        assert metadata['video_streams'][0]['fps'] == 30.0
    
    @patch('services.audio_extractor.ffmpeg')
    def test_extract_audio_segment_success(self, mock_ffmpeg):
        """测试音频片段提取成功"""
        mock_input = MagicMock()
        mock_output = MagicMock()
        mock_run = MagicMock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_run
        mock_run.run.return_value = None
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == self.mock_input_path or path == self.mock_output_path
            
            result = self.extractor.extract_audio_segment(
                self.mock_input_path, self.mock_output_path, 30.0, 10.0
            )
            
            assert result == self.mock_output_path
            mock_ffmpeg.input.assert_called_once_with(self.mock_input_path, ss=30.0, t=10.0)
    
    def test_extract_audio_segment_invalid_params(self):
        """测试无效的时间参数"""
        with pytest.raises(AudioExtractionError, match="无效的时间参数"):
            self.extractor.extract_audio_segment(self.mock_input_path, self.mock_output_path, -1.0, 10.0)
        
        with pytest.raises(AudioExtractionError, match="无效的时间参数"):
            self.extractor.extract_audio_segment(self.mock_input_path, self.mock_output_path, 30.0, 0.0)
    
    @patch('services.audio_extractor.ffmpeg')
    def test_normalize_audio_success(self, mock_ffmpeg):
        """测试音频标准化成功"""
        mock_input = MagicMock()
        mock_filter = MagicMock()
        mock_output = MagicMock()
        mock_run = MagicMock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.filter.return_value = mock_filter
        mock_filter.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_run
        mock_run.run.return_value = None
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == self.mock_input_path or path == self.mock_output_path
            
            result = self.extractor.normalize_audio(self.mock_input_path, self.mock_output_path, -18.0)
            
            assert result == self.mock_output_path
            mock_input.filter.assert_called_once_with('loudnorm', I=-18.0)
    
    def test_parse_fps(self):
        """测试帧率解析"""
        assert self.extractor._parse_fps("30/1") == 30.0
        assert self.extractor._parse_fps("25/1") == 25.0
        assert self.extractor._parse_fps("29.97") == 29.97
        assert self.extractor._parse_fps("invalid") == 0.0
        assert self.extractor._parse_fps("30/0") == 0.0
    
    @patch('services.audio_extractor.ffmpeg')
    def test_check_ffmpeg_available_true(self, mock_ffmpeg):
        """测试FFmpeg可用性检查 - 可用"""
        mock_ffmpeg.probe.return_value = {}
        
        assert self.extractor.check_ffmpeg_available() is True
    
    @patch('services.audio_extractor.ffmpeg')
    def test_check_ffmpeg_available_false(self, mock_ffmpeg):
        """测试FFmpeg可用性检查 - 不可用"""
        mock_ffmpeg.probe.side_effect = Exception("FFmpeg not found")
        
        assert self.extractor.check_ffmpeg_available() is False