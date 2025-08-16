import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pydub import AudioSegment
import numpy as np
from services.audio_optimizer import AudioOptimizer, AudioOptimizerError, OptimizationResult, QualityMetrics
from models.core import TimedSegment


class TestAudioOptimizer:
    
    def setup_method(self):
        # 模拟 FFmpeg 可用
        with patch('services.audio_optimizer.which', return_value='/usr/bin/ffmpeg'):
            self.optimizer = AudioOptimizer()
        
        # 创建测试数据
        self.test_segments = [
            TimedSegment(
                start_time=0.0,
                end_time=2.0,
                original_text="Hello world",
                translated_text="你好世界",
                confidence=-0.1,
                speaker_id="speaker_1"
            ),
            TimedSegment(
                start_time=2.0,
                end_time=4.0,
                original_text="How are you",
                translated_text="你好吗",
                confidence=-0.2,
                speaker_id="speaker_1"
            ),
            TimedSegment(
                start_time=4.0,
                end_time=6.0,
                original_text="I am fine",
                translated_text="我很好",
                confidence=-0.15,
                speaker_id="speaker_2"
            )
        ]
        
        # 创建测试音频
        self.test_audio = AudioSegment.silent(duration=6000)  # 6秒静音
    
    def test_initialization_with_ffmpeg(self):
        """测试有FFmpeg时的初始化"""
        with patch('services.audio_optimizer.which', return_value='/usr/bin/ffmpeg'):
            optimizer = AudioOptimizer()
            assert optimizer.speed_config['min_ratio'] == 0.8
            assert optimizer.speed_config['max_ratio'] == 1.2
            assert optimizer.background_config['detection_threshold'] == -30
    
    def test_initialization_without_ffmpeg(self):
        """测试没有FFmpeg时的初始化"""
        with patch('services.audio_optimizer.which', return_value=None):
            with pytest.raises(AudioOptimizerError, match="未找到 FFmpeg"):
                AudioOptimizer()
    
    @patch('services.audio_optimizer.AudioSegment.from_file')
    def test_optimize_audio_timing_success(self, mock_from_file):
        """测试成功的音频时序优化"""
        # 模拟音频文件
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)  # 6秒
        mock_audio.export = Mock()
        mock_from_file.return_value = mock_audio
        
        # 模拟质量分析
        with patch.object(self.optimizer, '_analyze_audio_quality') as mock_analyze:
            mock_quality = QualityMetrics(
                sample_rate=44100, bit_depth=16, dynamic_range=60.0,
                peak_level=-10.0, rms_level=-20.0, snr_estimate=25.0
            )
            mock_analyze.return_value = mock_quality
            
            # 模拟优化方法
            with patch.object(self.optimizer, '_optimize_with_background_preservation', return_value=mock_audio):
                with patch.object(self.optimizer, '_maintain_audio_quality', return_value=mock_audio):
                    
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                        input_path = temp_file.name
                    
                    try:
                        result = self.optimizer.optimize_audio_timing(
                            input_path, self.test_segments, preserve_background=True
                        )
                        
                        assert isinstance(result, OptimizationResult)
                        assert result.background_preserved is True
                        assert result.processing_time > 0
                        assert 'original_quality' in result.quality_metrics
                        assert 'final_quality' in result.quality_metrics
                        
                    finally:
                        os.unlink(input_path)
    
    def test_optimize_audio_timing_file_not_exists(self):
        """测试文件不存在的音频优化"""
        with pytest.raises(AudioOptimizerError, match="音频文件不存在"):
            self.optimizer.optimize_audio_timing("/nonexistent/file.mp3", self.test_segments)
    
    def test_optimize_audio_timing_empty_segments(self):
        """测试空片段列表的音频优化"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            input_path = temp_file.name
        
        try:
            with pytest.raises(AudioOptimizerError, match="目标片段列表为空"):
                self.optimizer.optimize_audio_timing(input_path, [])
        finally:
            os.unlink(input_path)
    
    @patch('services.audio_optimizer.AudioSegment.from_file')
    def test_adjust_audio_speed_range_success(self, mock_from_file):
        """测试成功的音频速度调整"""
        mock_audio = Mock()
        mock_audio.export = Mock()
        mock_from_file.return_value = mock_audio
        
        with patch.object(self.optimizer, '_adjust_speed_with_quality_preservation', return_value=mock_audio):
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                input_path = temp_file.name
            
            try:
                result_path = self.optimizer.adjust_audio_speed_range(
                    input_path, 1.1, preserve_quality=True
                )
                
                assert result_path.endswith('.mp3')
                assert os.path.exists(result_path)
                
                # 清理输出文件
                os.unlink(result_path)
                
            finally:
                os.unlink(input_path)
    
    def test_adjust_audio_speed_range_invalid_ratio(self):
        """测试无效速度比例的音频调整"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            input_path = temp_file.name
        
        try:
            # 测试超出最小范围
            with pytest.raises(AudioOptimizerError, match="速度比例超出范围"):
                self.optimizer.adjust_audio_speed_range(input_path, 0.5)
            
            # 测试超出最大范围
            with pytest.raises(AudioOptimizerError, match="速度比例超出范围"):
                self.optimizer.adjust_audio_speed_range(input_path, 1.5)
                
        finally:
            os.unlink(input_path)
    
    @patch('services.audio_optimizer.AudioSegment.from_file')
    def test_preserve_background_audio_success(self, mock_from_file):
        """测试成功的背景音频保留"""
        # 模拟语音音频和背景音频
        speech_audio = Mock()
        speech_audio.__len__ = Mock(return_value=6000)
        speech_audio.overlay = Mock(return_value=speech_audio)
        speech_audio.export = Mock()
        
        background_audio = Mock()
        background_audio.__len__ = Mock(return_value=5000)
        background_audio.__getitem__ = Mock(return_value=background_audio)
        background_audio.__sub__ = Mock(return_value=background_audio)
        
        mock_from_file.side_effect = [speech_audio, background_audio]
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as speech_file:
            speech_path = speech_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as bg_file:
            bg_path = bg_file.name
        
        try:
            result_path = self.optimizer.preserve_background_audio(
                speech_path, bg_path, mix_ratio=0.3
            )
            
            assert result_path.endswith('.mp3')
            assert os.path.exists(result_path)
            
            # 清理输出文件
            os.unlink(result_path)
            
        finally:
            os.unlink(speech_path)
            os.unlink(bg_path)
    
    def test_preserve_background_audio_invalid_mix_ratio(self):
        """测试无效混合比例的背景音频保留"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as speech_file:
            speech_path = speech_file.name
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as bg_file:
            bg_path = bg_file.name
        
        try:
            # 测试负数比例
            with pytest.raises(AudioOptimizerError, match="混合比例超出范围"):
                self.optimizer.preserve_background_audio(speech_path, bg_path, mix_ratio=-0.1)
            
            # 测试超出1.0的比例
            with pytest.raises(AudioOptimizerError, match="混合比例超出范围"):
                self.optimizer.preserve_background_audio(speech_path, bg_path, mix_ratio=1.5)
                
        finally:
            os.unlink(speech_path)
            os.unlink(bg_path)
    
    @patch('services.audio_optimizer.ffmpeg')
    def test_enhance_audio_quality_success(self, mock_ffmpeg):
        """测试成功的音频质量增强"""
        # 模拟FFmpeg操作
        mock_input = Mock()
        mock_filter = Mock()
        mock_filter_complex = Mock()
        mock_output = Mock()
        mock_overwrite = Mock()
        mock_run = Mock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.filter.return_value = mock_filter
        mock_filter.filter_complex.return_value = mock_filter_complex
        mock_filter_complex.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run = mock_run
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            input_path = temp_file.name
        
        try:
            result_path = self.optimizer.enhance_audio_quality(
                input_path, normalize=True, noise_reduction=True
            )
            
            assert result_path.endswith('.mp3')
            mock_ffmpeg.input.assert_called_with(input_path)
            
        finally:
            os.unlink(input_path)
    
    def test_enhance_audio_quality_file_not_exists(self):
        """测试文件不存在的音频质量增强"""
        with pytest.raises(AudioOptimizerError, match="音频文件不存在"):
            self.optimizer.enhance_audio_quality("/nonexistent/file.mp3")
    
    def test_analyze_audio_quality(self):
        """测试音频质量分析"""
        # 创建模拟音频
        mock_audio = Mock()
        mock_audio.frame_rate = 44100
        mock_audio.sample_width = 2  # 16-bit
        mock_audio.max_dBFS = -5.0
        mock_audio.dBFS = -15.0
        mock_audio.channels = 1
        mock_audio.get_array_of_samples.return_value = np.random.randint(-32768, 32767, 44100)
        
        quality = self.optimizer._analyze_audio_quality(mock_audio)
        
        assert isinstance(quality, QualityMetrics)
        assert quality.sample_rate == 44100
        assert quality.bit_depth == 16
        assert quality.peak_level == -5.0
        assert quality.rms_level == -15.0
        assert quality.dynamic_range > 0
        assert quality.snr_estimate > 0
    
    def test_analyze_audio_quality_exception_handling(self):
        """测试音频质量分析异常处理"""
        # 创建会抛出异常的模拟音频
        mock_audio = Mock()
        mock_audio.frame_rate = 44100
        mock_audio.sample_width = 2
        mock_audio.max_dBFS = -5.0
        mock_audio.dBFS = -15.0
        mock_audio.get_array_of_samples.side_effect = Exception("测试异常")
        
        quality = self.optimizer._analyze_audio_quality(mock_audio)
        
        # 应该返回默认值
        assert isinstance(quality, QualityMetrics)
        assert quality.sample_rate == 44100
        assert quality.bit_depth == 16
    
    def test_calculate_speed_adjustments(self):
        """测试计算速度调整"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=8000)  # 8秒，需要调整到6秒
        
        adjustments = self.optimizer._calculate_speed_adjustments(mock_audio, self.test_segments)
        
        assert len(adjustments) == len(self.test_segments)
        for i, ratio in adjustments:
            assert isinstance(i, int)
            assert isinstance(ratio, float)
            assert 0.8 <= ratio <= 1.2  # 在允许范围内
    
    def test_calculate_speed_adjustments_empty_segments(self):
        """测试空片段的速度调整计算"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)
        
        adjustments = self.optimizer._calculate_speed_adjustments(mock_audio, [])
        
        assert adjustments == []
    
    def test_adjust_speed_simple_speedup(self):
        """测试简单加速调整"""
        mock_audio = Mock()
        mock_audio.speedup = Mock(return_value=mock_audio)
        
        result = self.optimizer._adjust_speed_simple(mock_audio, 1.2)
        
        assert result is not None
        mock_audio.speedup.assert_called_once_with(playback_speed=1.2)
    
    def test_adjust_speed_simple_slowdown(self):
        """测试简单减速调整"""
        mock_audio = Mock()
        mock_audio.frame_rate = 44100
        mock_audio.raw_data = b"test_data"
        mock_audio._spawn = Mock(return_value=mock_audio)
        mock_audio.set_frame_rate = Mock(return_value=mock_audio)
        
        result = self.optimizer._adjust_speed_simple(mock_audio, 0.8)
        
        assert result is not None
        mock_audio._spawn.assert_called_once()
    
    def test_adjust_speed_simple_exception(self):
        """测试简单速度调整异常处理"""
        mock_audio = Mock()
        mock_audio.speedup.side_effect = Exception("测试异常")
        
        result = self.optimizer._adjust_speed_simple(mock_audio, 1.2)
        
        # 异常时应返回原音频
        assert result == mock_audio
    
    @patch('services.audio_optimizer.ffmpeg')
    def test_adjust_speed_with_ffmpeg_success(self, mock_ffmpeg):
        """测试使用FFmpeg的速度调整"""
        mock_audio = Mock()
        mock_audio.export = Mock()
        
        # 模拟FFmpeg操作
        mock_input = Mock()
        mock_filter = Mock()
        mock_output = Mock()
        mock_overwrite = Mock()
        mock_run = Mock()
        
        mock_ffmpeg.input.return_value = mock_input
        mock_input.filter.return_value = mock_filter
        mock_filter.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run = mock_run
        
        with patch('services.audio_optimizer.AudioSegment.from_wav', return_value=mock_audio):
            result = self.optimizer._adjust_speed_with_ffmpeg(mock_audio, 1.1)
            assert result is not None
    
    @patch('services.audio_optimizer.ffmpeg')
    def test_adjust_speed_with_ffmpeg_failure(self, mock_ffmpeg):
        """测试FFmpeg调整失败的情况"""
        mock_audio = Mock()
        mock_audio.export = Mock()
        
        # 模拟FFmpeg失败
        mock_ffmpeg.input.side_effect = Exception("FFmpeg错误")
        
        result = self.optimizer._adjust_speed_with_ffmpeg(mock_audio, 1.1)
        
        # 失败时应返回原音频
        assert result == mock_audio
    
    def test_maintain_audio_quality(self):
        """测试音频质量保持"""
        mock_audio = Mock()
        mock_audio.frame_rate = 44100
        mock_audio.dBFS = -25.0
        mock_audio.set_frame_rate = Mock(return_value=mock_audio)
        mock_audio.__add__ = Mock(return_value=mock_audio)
        
        target_quality = QualityMetrics(
            sample_rate=44100, bit_depth=16, dynamic_range=60.0,
            peak_level=-10.0, rms_level=-18.0, snr_estimate=25.0
        )
        
        result = self.optimizer._maintain_audio_quality(mock_audio, target_quality)
        
        assert result is not None
    
    def test_maintain_audio_quality_exception(self):
        """测试音频质量保持异常处理"""
        mock_audio = Mock()
        mock_audio.frame_rate = Mock(side_effect=Exception("测试异常"))
        
        target_quality = QualityMetrics(
            sample_rate=44100, bit_depth=16, dynamic_range=60.0,
            peak_level=-10.0, rms_level=-18.0, snr_estimate=25.0
        )
        
        result = self.optimizer._maintain_audio_quality(mock_audio, target_quality)
        
        # 异常时应返回原音频
        assert result == mock_audio
    
    def test_calculate_quality_preservation_score(self):
        """测试质量保持评分计算"""
        original = QualityMetrics(
            sample_rate=44100, bit_depth=16, dynamic_range=60.0,
            peak_level=-10.0, rms_level=-18.0, snr_estimate=25.0
        )
        
        # 测试质量保持良好的情况
        good_final = QualityMetrics(
            sample_rate=44100, bit_depth=16, dynamic_range=58.0,
            peak_level=-10.5, rms_level=-18.5, snr_estimate=24.0
        )
        
        score = self.optimizer._calculate_quality_preservation_score(original, good_final)
        assert 0.8 <= score <= 1.0
        
        # 测试质量下降的情况
        poor_final = QualityMetrics(
            sample_rate=22050, bit_depth=8, dynamic_range=30.0,
            peak_level=-15.0, rms_level=-25.0, snr_estimate=15.0
        )
        
        poor_score = self.optimizer._calculate_quality_preservation_score(original, poor_final)
        assert poor_score < 0.8
    
    def test_calculate_quality_preservation_score_exception(self):
        """测试质量保持评分计算异常处理"""
        original = Mock()
        original.sample_rate = Mock(side_effect=Exception("测试异常"))
        
        final = Mock()
        
        score = self.optimizer._calculate_quality_preservation_score(original, final)
        
        # 异常时应返回默认评分
        assert score == 0.7
    
    @patch('services.audio_optimizer.AudioSegment.from_file')
    def test_optimize_with_background_preservation(self, mock_from_file):
        """测试保留背景音的优化处理"""
        mock_audio = Mock()
        mock_from_file.return_value = mock_audio
        
        speed_adjustments = [(0, 1.1), (1, 1.1), (2, 1.1)]
        
        with patch.object(self.optimizer, '_adjust_speed_with_ffmpeg', return_value=mock_audio):
            result = self.optimizer._optimize_with_background_preservation(
                mock_audio, self.test_segments, speed_adjustments
            )
            
            assert result is not None
    
    @patch('services.audio_optimizer.AudioSegment.from_file')
    def test_optimize_simple_speed_adjustment(self, mock_from_file):
        """测试简单速度调整优化"""
        mock_audio = Mock()
        mock_from_file.return_value = mock_audio
        
        speed_adjustments = [(0, 1.1), (1, 1.1), (2, 1.1)]
        
        with patch.object(self.optimizer, '_adjust_speed_simple', return_value=mock_audio):
            result = self.optimizer._optimize_simple_speed_adjustment(
                mock_audio, self.test_segments, speed_adjustments
            )
            
            assert result is not None
    
    def test_optimize_simple_speed_adjustment_empty_adjustments(self):
        """测试无调整的简单速度优化"""
        mock_audio = Mock()
        
        result = self.optimizer._optimize_simple_speed_adjustment(
            mock_audio, self.test_segments, []
        )
        
        # 无调整时应返回原音频
        assert result == mock_audio