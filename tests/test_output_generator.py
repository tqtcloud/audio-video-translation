import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from services.output_generator import OutputGenerator, OutputGeneratorError, OutputResult, OutputConfig
from models.core import FileType


class TestOutputGenerator:
    
    def setup_method(self):
        # 创建临时输出目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试配置
        self.test_config = OutputConfig(
            output_directory=self.temp_dir,
            file_naming_pattern="{name}_translated_{timestamp}",
            audio_format="mp3",
            video_format="mp4",
            preserve_metadata=True,
            overwrite_existing=False
        )
        
        # 模拟 FFmpeg 可用
        with patch('services.output_generator.which', return_value='/usr/bin/ffmpeg'):
            self.generator = OutputGenerator(self.test_config)
    
    def test_initialization_with_config(self):
        """测试使用配置的初始化"""
        with patch('services.output_generator.which', return_value='/usr/bin/ffmpeg'):
            generator = OutputGenerator(self.test_config)
            assert generator.config.output_directory == self.temp_dir
            assert generator.config.audio_format == "mp3"
            assert generator.config.video_format == "mp4"
    
    def test_initialization_without_config(self):
        """测试不使用配置的初始化"""
        with patch('services.output_generator.which', return_value='/usr/bin/ffmpeg'):
            generator = OutputGenerator()
            assert generator.config.output_directory == "./output"
            assert generator.config.audio_format == "mp3"
            assert generator.config.video_format == "mp4"
    
    def test_initialization_without_ffmpeg(self):
        """测试没有FFmpeg时的初始化"""
        with patch('services.output_generator.which', return_value=None):
            with pytest.raises(OutputGeneratorError, match="未找到 FFmpeg"):
                OutputGenerator()
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_detect_file_type_video_by_extension(self, mock_probe):
        """测试通过扩展名检测视频文件类型"""
        file_type = self.generator._detect_file_type("/test/video.mp4")
        assert file_type == FileType.VIDEO
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_detect_file_type_audio_by_extension(self, mock_probe):
        """测试通过扩展名检测音频文件类型"""
        file_type = self.generator._detect_file_type("/test/audio.mp3")
        assert file_type == FileType.AUDIO
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_detect_file_type_by_probe_video(self, mock_probe):
        """测试通过probe检测视频文件类型"""
        mock_probe.return_value = {
            'streams': [
                {'codec_type': 'video'},
                {'codec_type': 'audio'}
            ]
        }
        file_type = self.generator._detect_file_type("/test/unknown.file")
        assert file_type == FileType.VIDEO
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_detect_file_type_by_probe_audio(self, mock_probe):
        """测试通过probe检测音频文件类型"""
        mock_probe.return_value = {
            'streams': [
                {'codec_type': 'audio'}
            ]
        }
        file_type = self.generator._detect_file_type("/test/unknown.file")
        assert file_type == FileType.AUDIO
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_detect_file_type_unknown(self, mock_probe):
        """测试检测未知文件类型"""
        mock_probe.side_effect = Exception("Unknown format")
        file_type = self.generator._detect_file_type("/test/unknown.file")
        assert file_type == FileType.UNKNOWN
    
    def test_generate_output_path_audio(self):
        """测试生成音频输出路径"""
        with patch('time.time', return_value=1234567890):
            output_path = self.generator._generate_output_path("/input/test.wav", "audio")
            expected_path = f"{self.temp_dir}/test_translated_1234567890.mp3"
            assert output_path == expected_path
    
    def test_generate_output_path_video(self):
        """测试生成视频输出路径"""
        with patch('time.time', return_value=1234567890):
            output_path = self.generator._generate_output_path("/input/test.avi", "video")
            expected_path = f"{self.temp_dir}/test_translated_1234567890.mp4"
            assert output_path == expected_path
    
    def test_get_unique_path(self):
        """测试获取唯一路径"""
        # 创建一个已存在的文件
        existing_path = os.path.join(self.temp_dir, "test.mp3")
        with open(existing_path, 'w') as f:
            f.write("test")
        
        unique_path = self.generator._get_unique_path(existing_path)
        expected_path = os.path.join(self.temp_dir, "test_1.mp3")
        assert unique_path == expected_path
    
    def test_get_output_path_suggestion(self):
        """测试获取输出路径建议"""
        with patch('time.time', return_value=1234567890):
            suggestion = self.generator.get_output_path_suggestion("/input/test.mp4", "video")
            expected_path = f"{self.temp_dir}/test_translated_1234567890.mp4"
            assert suggestion == expected_path
    
    @patch('services.output_generator.ffmpeg')
    def test_generate_output_audio_input(self, mock_ffmpeg):
        """测试音频输入的输出生成"""
        # 创建临时输入文件
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as translated_file:
            translated_path = translated_file.name
        
        try:
            # 模拟文件类型检测
            with patch.object(self.generator, '_detect_file_type', return_value=FileType.AUDIO):
                with patch.object(self.generator, '_generate_audio_output') as mock_generate:
                    mock_result = OutputResult(
                        output_path="/output/test.mp3",
                        original_input_path=input_path,
                        output_type="audio",
                        file_size_bytes=1024,
                        processing_time=0.0,
                        quality_preserved=True,
                        format_info={},
                        metadata={}
                    )
                    mock_generate.return_value = mock_result
                    
                    result = self.generator.generate_output(input_path, translated_path)
                    
                    assert isinstance(result, OutputResult)
                    assert result.output_type == "audio"
                    assert result.processing_time > 0
                    
        finally:
            os.unlink(input_path)
            os.unlink(translated_path)
    
    @patch('services.output_generator.ffmpeg')
    def test_generate_output_video_input(self, mock_ffmpeg):
        """测试视频输入的输出生成"""
        # 创建临时输入文件
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as translated_file:
            translated_path = translated_file.name
        
        try:
            # 模拟文件类型检测
            with patch.object(self.generator, '_detect_file_type', return_value=FileType.VIDEO):
                with patch.object(self.generator, '_generate_video_output') as mock_generate:
                    mock_result = OutputResult(
                        output_path="/output/test.mp4",
                        original_input_path=input_path,
                        output_type="video",
                        file_size_bytes=2048,
                        processing_time=0.0,
                        quality_preserved=True,
                        format_info={},
                        metadata={}
                    )
                    mock_generate.return_value = mock_result
                    
                    result = self.generator.generate_output(input_path, translated_path)
                    
                    assert isinstance(result, OutputResult)
                    assert result.output_type == "video"
                    assert result.processing_time > 0
                    
        finally:
            os.unlink(input_path)
            os.unlink(translated_path)
    
    def test_generate_output_input_not_exists(self):
        """测试输入文件不存在的情况"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as translated_file:
            translated_path = translated_file.name
        
        try:
            with pytest.raises(OutputGeneratorError, match="输入文件不存在"):
                self.generator.generate_output("/nonexistent/file.mp3", translated_path)
        finally:
            os.unlink(translated_path)
    
    def test_generate_output_translated_audio_not_exists(self):
        """测试翻译音频文件不存在的情况"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as input_file:
            input_path = input_file.name
        
        try:
            with pytest.raises(OutputGeneratorError, match="翻译音频文件不存在"):
                self.generator.generate_output(input_path, "/nonexistent/audio.mp3")
        finally:
            os.unlink(input_path)
    
    @patch('services.output_generator.ffmpeg')
    def test_generate_audio_output_success(self, mock_ffmpeg):
        """测试成功的音频输出生成"""
        # 创建临时输入文件
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as translated_file:
            translated_path = translated_file.name
        
        try:
            # 模拟FFmpeg操作
            mock_input = Mock()
            mock_output = Mock()
            mock_overwrite = Mock()
            mock_run = Mock()
            
            mock_ffmpeg.input.return_value = mock_input
            mock_input.output.return_value = mock_output
            mock_output.overwrite_output.return_value = mock_overwrite
            mock_overwrite.run = mock_run
            
            # 模拟生成的输出文件
            output_path = os.path.join(self.temp_dir, "test_output.mp3")
            with open(output_path, 'w') as f:
                f.write("test audio output")
            
            with patch.object(self.generator, '_generate_output_path', return_value=output_path):
                with patch.object(self.generator, '_get_audio_format_info', return_value={}):
                    with patch.object(self.generator, '_extract_audio_metadata', return_value={}):
                        result = self.generator._generate_audio_output(input_path, translated_path)
                        
                        assert isinstance(result, OutputResult)
                        assert result.output_type == "audio"
                        assert result.quality_preserved is True
                        assert os.path.exists(result.output_path)
                        
        finally:
            os.unlink(input_path)
            os.unlink(translated_path)
    
    @patch('services.output_generator.ffmpeg')
    def test_generate_video_output_success(self, mock_ffmpeg):
        """测试成功的视频输出生成"""
        # 创建临时输入文件
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as translated_file:
            translated_path = translated_file.name
        
        try:
            # 模拟FFmpeg操作
            mock_video_input = Mock()
            mock_audio_input = Mock()
            mock_video = Mock()
            mock_audio = Mock()
            mock_output = Mock()
            mock_overwrite = Mock()
            mock_run = Mock()
            
            mock_ffmpeg.input.side_effect = [mock_video_input, mock_audio_input]
            mock_video_input.video = mock_video
            mock_audio_input.audio = mock_audio
            mock_ffmpeg.output.return_value = mock_output
            mock_output.overwrite_output.return_value = mock_overwrite
            mock_overwrite.run = mock_run
            
            # 模拟生成的输出文件
            output_path = os.path.join(self.temp_dir, "test_output.mp4")
            with open(output_path, 'w') as f:
                f.write("test video output")
            
            with patch.object(self.generator, '_generate_output_path', return_value=output_path):
                with patch.object(self.generator, '_verify_video_output_quality', return_value=True):
                    with patch.object(self.generator, '_get_video_format_info', return_value={}):
                        with patch.object(self.generator, '_extract_video_metadata', return_value={}):
                            result = self.generator._generate_video_output(input_path, translated_path)
                            
                            assert isinstance(result, OutputResult)
                            assert result.output_type == "video"
                            assert result.quality_preserved is True
                            assert os.path.exists(result.output_path)
                        
        finally:
            os.unlink(input_path)
            os.unlink(translated_path)
    
    @patch('services.output_generator.ffmpeg')
    def test_copy_audio_with_quality(self, mock_ffmpeg):
        """测试复制音频并调整质量"""
        # 模拟FFmpeg操作
        mock_input = Mock()
        mock_output = Mock()
        mock_overwrite = Mock()
        mock_run = Mock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run = mock_run
        
        quality_config = {'audio_bitrate': '192k'}
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            self.generator._copy_audio_with_quality(input_path, output_path, quality_config)
            mock_ffmpeg.input.assert_called_with(input_path)
            
        finally:
            os.unlink(input_path)
            os.unlink(output_path)
    
    @patch('services.output_generator.ffmpeg')
    def test_convert_audio_format(self, mock_ffmpeg):
        """测试音频格式转换"""
        # 模拟FFmpeg操作
        mock_input = Mock()
        mock_output = Mock()
        mock_overwrite = Mock()
        mock_run = Mock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run = mock_run
        
        quality_config = {'audio_bitrate': '192k'}
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            self.generator._convert_audio_format(input_path, output_path, quality_config)
            mock_ffmpeg.input.assert_called_with(input_path)
            
        finally:
            os.unlink(input_path)
            os.unlink(output_path)
    
    @patch('services.output_generator.ffmpeg')
    def test_replace_video_audio_track(self, mock_ffmpeg):
        """测试替换视频音频轨道"""
        # 模拟FFmpeg操作
        mock_video_input = Mock()
        mock_audio_input = Mock()
        mock_video = Mock()
        mock_audio = Mock()
        mock_output = Mock()
        mock_overwrite = Mock()
        mock_run = Mock()
        
        mock_ffmpeg.input.side_effect = [mock_video_input, mock_audio_input]
        mock_video_input.video = mock_video
        mock_audio_input.audio = mock_audio
        mock_ffmpeg.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run = mock_run
        
        quality_config = {'audio_bitrate': '192k'}
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
            video_path = video_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as audio_file:
            audio_path = audio_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            self.generator._replace_video_audio_track(
                video_path, audio_path, output_path, quality_config
            )
            
            assert mock_ffmpeg.input.call_count == 2
            mock_ffmpeg.output.assert_called_once()
            
        finally:
            os.unlink(video_path)
            os.unlink(audio_path)
            os.unlink(output_path)
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_verify_video_output_quality_good(self, mock_probe):
        """测试良好的视频输出质量验证"""
        # 模拟probe结果
        mock_probe.side_effect = [
            # 原始视频信息
            {
                'format': {'duration': '10.0'},
                'streams': [
                    {
                        'codec_type': 'video',
                        'width': 1920,
                        'height': 1080
                    }
                ]
            },
            # 输出视频信息
            {
                'format': {'duration': '10.1'},  # 略微不同的时长
                'streams': [
                    {
                        'codec_type': 'video',
                        'width': 1920,
                        'height': 1080
                    }
                ]
            }
        ]
        
        quality = self.generator._verify_video_output_quality(
            "/original/video.mp4", "/output/video.mp4"
        )
        assert quality is True
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_verify_video_output_quality_poor(self, mock_probe):
        """测试较差的视频输出质量验证"""
        # 模拟probe结果
        mock_probe.side_effect = [
            # 原始视频信息
            {
                'format': {'duration': '10.0'},
                'streams': [
                    {
                        'codec_type': 'video',
                        'width': 1920,
                        'height': 1080
                    }
                ]
            },
            # 输出视频信息
            {
                'format': {'duration': '15.0'},  # 时长差异过大
                'streams': [
                    {
                        'codec_type': 'video',
                        'width': 1280,  # 不同的分辨率
                        'height': 720
                    }
                ]
            }
        ]
        
        quality = self.generator._verify_video_output_quality(
            "/original/video.mp4", "/output/video.mp4"
        )
        assert quality is False
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_get_audio_format_info(self, mock_probe):
        """测试获取音频格式信息"""
        mock_probe.return_value = {
            'format': {
                'duration': '5.5',
                'format_name': 'mp3'
            },
            'streams': [
                {
                    'codec_type': 'audio',
                    'codec_name': 'mp3',
                    'sample_rate': '44100',
                    'channels': '2',
                    'bit_rate': '192000'
                }
            ]
        }
        
        info = self.generator._get_audio_format_info("/test/audio.mp3")
        
        assert info['codec'] == 'mp3'
        assert info['sample_rate'] == 44100
        assert info['channels'] == 2
        assert info['bitrate'] == 192000
        assert info['duration'] == 5.5
        assert info['format'] == 'mp3'
    
    @patch('services.output_generator.ffmpeg.probe')
    def test_get_video_format_info(self, mock_probe):
        """测试获取视频格式信息"""
        mock_probe.return_value = {
            'format': {
                'duration': '10.0',
                'format_name': 'mov,mp4,m4a,3gp,3g2,mj2'
            },
            'streams': [
                {
                    'codec_type': 'video',
                    'codec_name': 'h264',
                    'width': '1920',
                    'height': '1080',
                    'r_frame_rate': '30/1'
                },
                {
                    'codec_type': 'audio',
                    'codec_name': 'aac',
                    'sample_rate': '44100',
                    'channels': '2'
                }
            ]
        }
        
        info = self.generator._get_video_format_info("/test/video.mp4")
        
        assert info['video_codec'] == 'h264'
        assert info['width'] == 1920
        assert info['height'] == 1080
        assert info['fps'] == 30.0
        assert info['duration'] == 10.0
        assert info['format'] == 'mov'
        assert info['audio_codec'] == 'aac'
        assert info['audio_sample_rate'] == 44100
        assert info['audio_channels'] == 2
    
    def test_set_output_config(self):
        """测试设置输出配置"""
        new_config = OutputConfig(
            output_directory="/new/output",
            file_naming_pattern="{name}_{type}",
            audio_format="wav"
        )
        
        with patch.object(self.generator, '_ensure_output_directory'):
            self.generator.set_output_config(new_config)
            assert self.generator.config.output_directory == "/new/output"
            assert self.generator.config.audio_format == "wav"
    
    def test_cleanup_temp_files(self):
        """测试清理临时文件"""
        # 创建临时文件
        temp_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp_files.append(f.name)
        
        # 验证文件存在
        for temp_file in temp_files:
            assert os.path.exists(temp_file)
        
        # 清理文件
        self.generator.cleanup_temp_files(temp_files)
        
        # 验证文件已删除
        for temp_file in temp_files:
            assert not os.path.exists(temp_file)
    
    def test_cleanup_temp_files_with_nonexistent(self):
        """测试清理包含不存在文件的临时文件列表"""
        # 创建一个存在的临时文件和一个不存在的文件路径
        with tempfile.NamedTemporaryFile(delete=False) as f:
            existing_file = f.name
        
        nonexistent_file = "/path/to/nonexistent/file.tmp"
        temp_files = [existing_file, nonexistent_file]
        
        # 应该不抛出异常
        self.generator.cleanup_temp_files(temp_files)
        
        # 验证存在的文件已删除
        assert not os.path.exists(existing_file)
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass