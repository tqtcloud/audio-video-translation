import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from services.video_assembler import VideoAssembler, VideoAssemblerError, AudioReplacementResult, VideoInfo
from models.core import FileType


class TestVideoAssembler:
    
    def setup_method(self):
        # 模拟 FFmpeg 可用
        with patch('services.video_assembler.which', return_value='/usr/bin/ffmpeg'):
            self.assembler = VideoAssembler()
        
        # 创建测试视频信息
        self.test_video_info = VideoInfo(
            width=1920,
            height=1080,
            fps=30.0,
            duration=10.0,
            codec='h264',
            bitrate=5000000,
            format='mp4'
        )
    
    def test_initialization_with_ffmpeg(self):
        """测试有FFmpeg时的初始化"""
        with patch('services.video_assembler.which', return_value='/usr/bin/ffmpeg'):
            assembler = VideoAssembler()
            assert 'mp4' in assembler.supported_video_formats
            assert 'mp3' in assembler.supported_audio_formats
            assert assembler.video_config['preserve_quality'] is True
    
    def test_initialization_without_ffmpeg(self):
        """测试没有FFmpeg时的初始化"""
        with patch('services.video_assembler.which', return_value=None):
            with pytest.raises(VideoAssemblerError, match="未找到 FFmpeg"):
                VideoAssembler()
    
    @patch('services.video_assembler.ffmpeg')
    def test_replace_audio_track_success(self, mock_ffmpeg):
        """测试成功的音频轨道替换"""
        # 模拟视频和音频信息
        with patch.object(self.assembler, '_get_video_info', return_value=self.test_video_info):
            with patch.object(self.assembler, '_get_audio_info', return_value={'codec': 'mp3', 'duration': 10.0}):
                with patch.object(self.assembler, '_check_format_compatibility', return_value=True):
                    with patch.object(self.assembler, '_replace_audio_with_quality_preservation'):
                        with patch.object(self.assembler, '_verify_output_quality', return_value=True):
                            
                            # 创建临时文件
                            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
                                video_path = video_file.name
                            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as audio_file:
                                audio_path = audio_file.name
                            
                            try:
                                result = self.assembler.replace_audio_track(
                                    video_path, audio_path, preserve_quality=True
                                )
                                
                                assert isinstance(result, AudioReplacementResult)
                                assert result.quality_preserved is True
                                assert result.format_compatibility is True
                                assert result.processing_time > 0
                                assert 'width' in result.original_video_info
                                
                            finally:
                                os.unlink(video_path)
                                os.unlink(audio_path)
    
    def test_replace_audio_track_video_not_exists(self):
        """测试视频文件不存在的音频替换"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as audio_file:
            audio_path = audio_file.name
        
        try:
            with pytest.raises(VideoAssemblerError, match="视频文件不存在"):
                self.assembler.replace_audio_track("/nonexistent/video.mp4", audio_path)
        finally:
            os.unlink(audio_path)
    
    def test_replace_audio_track_audio_not_exists(self):
        """测试音频文件不存在的音频替换"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
            video_path = video_file.name
        
        try:
            with pytest.raises(VideoAssemblerError, match="音频文件不存在"):
                self.assembler.replace_audio_track(video_path, "/nonexistent/audio.mp3")
        finally:
            os.unlink(video_path)
    
    @patch('services.video_assembler.ffmpeg')
    def test_extract_video_stream_success(self, mock_ffmpeg):
        """测试成功的视频流提取"""
        # 模拟FFmpeg操作
        mock_input = Mock()
        mock_video = Mock()
        mock_output = Mock()
        mock_overwrite = Mock()
        mock_run = Mock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.video = mock_video
        mock_video.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run = mock_run
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
            video_path = video_file.name
        
        try:
            result_path = self.assembler.extract_video_stream(video_path)
            
            assert result_path.endswith('.mp4')
            mock_ffmpeg.input.assert_called_with(video_path)
            
        finally:
            os.unlink(video_path)
    
    def test_extract_video_stream_file_not_exists(self):
        """测试文件不存在的视频流提取"""
        with pytest.raises(VideoAssemblerError, match="视频文件不存在"):
            self.assembler.extract_video_stream("/nonexistent/video.mp4")
    
    @patch('services.video_assembler.ffmpeg')
    def test_merge_video_audio_success(self, mock_ffmpeg):
        """测试成功的视频音频合并"""
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
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
            video_path = video_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as audio_file:
            audio_path = audio_file.name
        
        try:
            result_path = self.assembler.merge_video_audio(video_path, audio_path)
            
            assert result_path.endswith('.mp4')
            assert mock_ffmpeg.input.call_count == 2
            
        finally:
            os.unlink(video_path)
            os.unlink(audio_path)
    
    @patch('services.video_assembler.ffmpeg')
    def test_merge_video_audio_with_sync_offset(self, mock_ffmpeg):
        """测试带同步偏移的视频音频合并"""
        # 模拟FFmpeg操作
        mock_video_input = Mock()
        mock_audio_input = Mock()
        mock_video = Mock()
        mock_audio = Mock()
        mock_filter = Mock()
        mock_output = Mock()
        mock_overwrite = Mock()
        mock_run = Mock()
        
        mock_ffmpeg.input.side_effect = [mock_video_input, mock_audio_input]
        mock_video_input.video = mock_video
        mock_audio_input.filter.return_value = mock_filter
        mock_filter.audio = mock_audio
        mock_ffmpeg.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run = mock_run
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
            video_path = video_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as audio_file:
            audio_path = audio_file.name
        
        try:
            result_path = self.assembler.merge_video_audio(
                video_path, audio_path, sync_offset=0.5
            )
            
            assert result_path.endswith('.mp4')
            mock_audio_input.filter.assert_called_with('adelay', '500|500')
            
        finally:
            os.unlink(video_path)
            os.unlink(audio_path)
    
    @patch('services.video_assembler.ffmpeg')
    def test_convert_video_format_success(self, mock_ffmpeg):
        """测试成功的视频格式转换"""
        # 模拟FFmpeg操作
        mock_input = Mock()
        mock_output = Mock()
        mock_overwrite = Mock()
        mock_run = Mock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run = mock_run
        
        with tempfile.NamedTemporaryFile(suffix='.avi', delete=False) as video_file:
            video_path = video_file.name
        
        try:
            result_path = self.assembler.convert_video_format(
                video_path, 'mp4', preserve_quality=True
            )
            
            assert result_path.endswith('.mp4')
            mock_ffmpeg.input.assert_called_with(video_path)
            
        finally:
            os.unlink(video_path)
    
    def test_convert_video_format_unsupported(self):
        """测试不支持格式的视频转换"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
            video_path = video_file.name
        
        try:
            with pytest.raises(VideoAssemblerError, match="不支持的目标格式"):
                self.assembler.convert_video_format(video_path, 'unsupported')
        finally:
            os.unlink(video_path)
    
    @patch('services.video_assembler.ffmpeg.probe')
    def test_get_video_metadata_success(self, mock_probe):
        """测试成功的视频元数据获取"""
        # 模拟probe结果
        mock_probe.return_value = {
            'format': {
                'duration': '10.5',
                'size': '50000000',
                'bit_rate': '5000000'
            },
            'streams': [
                {
                    'codec_type': 'video',
                    'width': 1920,
                    'height': 1080,
                    'codec_name': 'h264'
                },
                {
                    'codec_type': 'audio',
                    'codec_name': 'aac',
                    'channels': 2
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
            video_path = video_file.name
        
        try:
            metadata = self.assembler.get_video_metadata(video_path)
            
            assert metadata['duration'] == 10.5
            assert metadata['size'] == 50000000
            assert metadata['video_stream']['width'] == 1920
            assert metadata['audio_stream']['codec_name'] == 'aac'
            
        finally:
            os.unlink(video_path)
    
    @patch('services.video_assembler.ffmpeg.probe')
    def test_get_video_info(self, mock_probe):
        """测试获取视频信息"""
        # 模拟probe结果
        mock_probe.return_value = {
            'format': {
                'duration': '10.5',
                'format_name': 'mov,mp4,m4a,3gp,3g2,mj2'
            },
            'streams': [
                {
                    'codec_type': 'video',
                    'width': 1920,
                    'height': 1080,
                    'r_frame_rate': '30/1',
                    'codec_name': 'h264',
                    'bit_rate': '5000000'
                }
            ]
        }
        
        video_info = self.assembler._get_video_info("/fake/path.mp4")
        
        assert isinstance(video_info, VideoInfo)
        assert video_info.width == 1920
        assert video_info.height == 1080
        assert video_info.fps == 30.0
        assert video_info.duration == 10.5
        assert video_info.codec == 'h264'
        assert video_info.bitrate == 5000000
        assert video_info.format == 'mov'
    
    @patch('services.video_assembler.ffmpeg.probe')
    def test_get_audio_info(self, mock_probe):
        """测试获取音频信息"""
        # 模拟probe结果
        mock_probe.return_value = {
            'format': {
                'duration': '8.5'
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
        
        audio_info = self.assembler._get_audio_info("/fake/path.mp3")
        
        assert audio_info['codec'] == 'mp3'
        assert audio_info['sample_rate'] == 44100
        assert audio_info['channels'] == 2
        assert audio_info['duration'] == 8.5
        assert audio_info['bitrate'] == 192000
    
    def test_check_format_compatibility_supported(self):
        """测试支持格式的兼容性检查"""
        compatibility = self.assembler._check_format_compatibility(
            "/fake/video.mp4", "/fake/audio.mp3"
        )
        assert compatibility is True
    
    def test_check_format_compatibility_unsupported(self):
        """测试不支持格式的兼容性检查"""
        compatibility = self.assembler._check_format_compatibility(
            "/fake/video.unsupported", "/fake/audio.unknown"
        )
        assert compatibility is False
    
    @patch('services.video_assembler.ffmpeg')
    def test_replace_audio_with_quality_preservation(self, mock_ffmpeg):
        """测试保持质量的音频替换"""
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
        
        with patch.object(self.assembler, '_get_audio_duration', return_value=10.0):
            self.assembler._replace_audio_with_quality_preservation(
                "/fake/video.mp4", "/fake/audio.mp3", "/fake/output.mp4", self.test_video_info
            )
            
            mock_ffmpeg.output.assert_called_once()
    
    @patch('services.video_assembler.ffmpeg')
    def test_replace_audio_simple(self, mock_ffmpeg):
        """测试简单音频替换"""
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
        
        self.assembler._replace_audio_simple(
            "/fake/video.mp4", "/fake/audio.mp3", "/fake/output.mp4"
        )
        
        mock_ffmpeg.output.assert_called_once()
    
    def test_verify_output_quality_good(self):
        """测试良好的输出质量验证"""
        output_info = VideoInfo(
            width=1920,
            height=1080,
            fps=30.0,
            duration=10.1,  # 略微不同的时长
            codec='h264',
            bitrate=5000000,
            format='mp4'
        )
        
        with patch.object(self.assembler, '_get_video_info', return_value=output_info):
            quality_preserved = self.assembler._verify_output_quality(
                "/fake/original.mp4", "/fake/output.mp4", self.test_video_info
            )
            
            assert quality_preserved is True
    
    def test_verify_output_quality_poor(self):
        """测试较差的输出质量验证"""
        output_info = VideoInfo(
            width=1280,  # 不同的分辨率
            height=720,
            fps=25.0,    # 不同的帧率
            duration=15.0,  # 差异过大的时长
            codec='h264',
            bitrate=5000000,
            format='mp4'
        )
        
        with patch.object(self.assembler, '_get_video_info', return_value=output_info):
            quality_preserved = self.assembler._verify_output_quality(
                "/fake/original.mp4", "/fake/output.mp4", self.test_video_info
            )
            
            assert quality_preserved is False
    
    def test_verify_output_quality_exception(self):
        """测试输出质量验证异常处理"""
        with patch.object(self.assembler, '_get_video_info', side_effect=Exception("测试异常")):
            quality_preserved = self.assembler._verify_output_quality(
                "/fake/original.mp4", "/fake/output.mp4", self.test_video_info
            )
            
            assert quality_preserved is False
    
    @patch('services.video_assembler.ffmpeg.probe')
    def test_get_audio_duration(self, mock_probe):
        """测试获取音频时长"""
        mock_probe.return_value = {
            'format': {
                'duration': '8.5'
            }
        }
        
        duration = self.assembler._get_audio_duration("/fake/audio.mp3")
        assert duration == 8.5
    
    def test_get_audio_duration_exception(self):
        """测试获取音频时长异常处理"""
        with patch('services.video_assembler.ffmpeg.probe', side_effect=Exception("测试异常")):
            duration = self.assembler._get_audio_duration("/fake/audio.mp3")
            assert duration == 0.0
    
    def test_can_copy_codec_compatible(self):
        """测试兼容编解码器检查"""
        with patch.object(self.assembler, '_get_video_info', return_value=self.test_video_info):
            can_copy = self.assembler._can_copy_codec("/fake/video.mp4", "mp4")
            assert can_copy is True
    
    def test_can_copy_codec_incompatible(self):
        """测试不兼容编解码器检查"""
        incompatible_info = VideoInfo(
            width=1920, height=1080, fps=30.0, duration=10.0,
            codec='vp9', bitrate=5000000, format='mp4'  # VP9编解码器
        )
        
        with patch.object(self.assembler, '_get_video_info', return_value=incompatible_info):
            can_copy = self.assembler._can_copy_codec("/fake/video.mp4", "avi")
            assert can_copy is False
    
    def test_can_copy_codec_exception(self):
        """测试编解码器检查异常处理"""
        with patch.object(self.assembler, '_get_video_info', side_effect=Exception("测试异常")):
            can_copy = self.assembler._can_copy_codec("/fake/video.mp4", "mp4")
            assert can_copy is False