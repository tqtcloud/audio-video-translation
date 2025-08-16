import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pydub import AudioSegment
import numpy as np
from services.audio_synchronizer import AudioSynchronizer, AudioSynchronizerError, SyncAnalysisResult, AudioAdjustmentResult
from models.core import TimedSegment


class TestAudioSynchronizer:
    
    def setup_method(self):
        # 模拟 FFmpeg 可用
        with patch('services.audio_synchronizer.which', return_value='/usr/bin/ffmpeg'):
            self.synchronizer = AudioSynchronizer()
        
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
        with patch('services.audio_synchronizer.which', return_value='/usr/bin/ffmpeg'):
            synchronizer = AudioSynchronizer()
            assert synchronizer.sync_config['timing_tolerance'] == 0.1
            assert synchronizer.adjustment_config['min_speed'] == 0.8
            assert synchronizer.adjustment_config['max_speed'] == 1.2
    
    def test_initialization_without_ffmpeg(self):
        """测试没有FFmpeg时的初始化"""
        with patch('services.audio_synchronizer.which', return_value=None):
            with pytest.raises(AudioSynchronizerError, match="未找到 FFmpeg"):
                AudioSynchronizer()
    
    @patch('services.audio_synchronizer.AudioSegment.from_file')
    def test_analyze_sync_quality_success(self, mock_from_file):
        """测试成功的同步质量分析"""
        # 模拟音频文件
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)  # 6秒
        mock_from_file.return_value = mock_audio
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = self.synchronizer.analyze_sync_quality(
                self.test_segments, temp_path
            )
            
            assert isinstance(result, SyncAnalysisResult)
            assert 0.0 <= result.timing_accuracy <= 1.0
            assert 0.0 <= result.sync_quality_score <= 1.0
            assert result.processing_time > 0
            assert len(result.segment_offsets) == len(self.test_segments)
            
        finally:
            os.unlink(temp_path)
    
    def test_analyze_sync_quality_empty_segments(self):
        """测试空片段列表的同步分析"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            with pytest.raises(AudioSynchronizerError, match="原始片段列表为空"):
                self.synchronizer.analyze_sync_quality([], temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_analyze_sync_quality_file_not_exists(self):
        """测试文件不存在的同步分析"""
        with pytest.raises(AudioSynchronizerError, match="翻译音频文件不存在"):
            self.synchronizer.analyze_sync_quality(self.test_segments, "/nonexistent/file.mp3")
    
    @patch('services.audio_synchronizer.AudioSegment.from_file')
    def test_adjust_audio_timing_no_adjustment_needed(self, mock_from_file):
        """测试不需要调整的音频时序"""
        # 模拟音频文件，时长刚好匹配
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)  # 6秒，匹配目标时长
        mock_audio.export = Mock()
        mock_from_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            input_path = temp_file.name
        
        try:
            result = self.synchronizer.adjust_audio_timing(input_path, self.test_segments)
            
            assert isinstance(result, AudioAdjustmentResult)
            assert result.speed_adjustment == 1.0
            assert result.quality_preserved is True
            assert result.processing_time > 0
            assert 'speed_ratio' in result.adjustment_details
            
        finally:
            os.unlink(input_path)
    
    @patch('services.audio_synchronizer.AudioSegment.from_file')
    def test_adjust_audio_timing_with_speed_adjustment(self, mock_from_file):
        """测试需要速度调整的音频时序"""
        # 模拟音频文件，时长需要调整
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=8000)  # 8秒，需要加速到6秒
        mock_audio.export = Mock()
        mock_from_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            input_path = temp_file.name
        
        # 模拟音频调整方法
        with patch.object(self.synchronizer, '_adjust_audio_speed', return_value=mock_audio):
            with patch.object(self.synchronizer, '_verify_audio_quality', return_value=True):
                try:
                    result = self.synchronizer.adjust_audio_timing(input_path, self.test_segments)
                    
                    assert isinstance(result, AudioAdjustmentResult)
                    assert result.speed_adjustment != 1.0
                    assert result.quality_preserved is True
                    assert result.processing_time > 0
                    
                finally:
                    os.unlink(input_path)
    
    def test_adjust_audio_timing_file_not_exists(self):
        """测试文件不存在的音频调整"""
        with pytest.raises(AudioSynchronizerError, match="音频文件不存在"):
            self.synchronizer.adjust_audio_timing("/nonexistent/file.mp3", self.test_segments)
    
    def test_adjust_audio_timing_empty_segments(self):
        """测试空片段列表的音频调整"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            input_path = temp_file.name
        
        try:
            with pytest.raises(AudioSynchronizerError, match="目标片段列表为空"):
                self.synchronizer.adjust_audio_timing(input_path, [])
        finally:
            os.unlink(input_path)
    
    def test_generate_sync_report_excellent_quality(self):
        """测试生成优秀质量的同步报告"""
        analysis_result = SyncAnalysisResult(
            timing_accuracy=0.95,
            avg_offset=0.05,
            max_offset=0.1,
            sync_quality_score=0.95,
            segment_offsets=[(0, 0.02), (1, -0.03), (2, 0.05)],
            issues_detected=[],
            processing_time=1.5
        )
        
        report = self.synchronizer.generate_sync_report(analysis_result, self.test_segments)
        
        assert report['summary']['overall_quality'] == 'excellent'
        assert report['summary']['sync_quality_score'] == 0.95
        assert report['summary']['total_segments'] == 3
        assert 'timing_analysis' in report
        assert 'quality_metrics' in report
        assert 'recommendations' in report
        assert 'processing_info' in report
    
    def test_generate_sync_report_poor_quality(self):
        """测试生成较差质量的同步报告"""
        analysis_result = SyncAnalysisResult(
            timing_accuracy=0.3,
            avg_offset=0.8,
            max_offset=1.5,
            sync_quality_score=0.2,
            segment_offsets=[(0, 0.8), (1, -1.2), (2, 1.5)],
            issues_detected=["整体时序准确性较低", "平均时序偏移过大"],
            processing_time=1.5
        )
        
        report = self.synchronizer.generate_sync_report(analysis_result, self.test_segments)
        
        assert report['summary']['overall_quality'] == 'poor'
        assert len(report['issues_detected']) > 0
        assert len(report['recommendations']) > 0
        assert report['quality_metrics']['segments_with_major_issues'] > 0
    
    def test_analyze_segment_offsets(self):
        """测试片段偏移分析"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)  # 6秒
        
        offsets = self.synchronizer._analyze_segment_offsets(
            self.test_segments, mock_audio, None
        )
        
        assert len(offsets) == len(self.test_segments)
        for i, offset in offsets:
            assert isinstance(i, int)
            assert isinstance(offset, float)
            assert 0 <= i < len(self.test_segments)
    
    def test_calculate_timing_accuracy(self):
        """测试时序准确性计算"""
        segment_offsets = [(0, 0.1), (1, -0.05), (2, 0.15)]
        
        accuracy = self.synchronizer._calculate_timing_accuracy(
            self.test_segments, 6.0, segment_offsets
        )
        
        assert 0.0 <= accuracy <= 1.0
    
    def test_calculate_timing_accuracy_empty_input(self):
        """测试空输入的时序准确性计算"""
        accuracy = self.synchronizer._calculate_timing_accuracy([], 0.0, [])
        assert accuracy == 0.0
    
    def test_calculate_sync_quality_score(self):
        """测试同步质量评分计算"""
        score = self.synchronizer._calculate_sync_quality_score(0.9, 0.1, 0.2)
        assert 0.0 <= score <= 1.0
        
        # 测试极端情况
        perfect_score = self.synchronizer._calculate_sync_quality_score(1.0, 0.0, 0.0)
        assert perfect_score > 0.8
        
        poor_score = self.synchronizer._calculate_sync_quality_score(0.1, 1.0, 2.0)
        assert poor_score < 0.5
    
    def test_detect_sync_issues(self):
        """测试同步问题检测"""
        # 测试有问题的情况
        issues = self.synchronizer._detect_sync_issues(
            [(0, 0.8), (1, 1.2), (2, 0.9)], 0.8, 1.2, 0.3
        )
        
        assert len(issues) > 0
        assert any("时序准确性较低" in issue for issue in issues)
        
        # 测试正常情况
        good_issues = self.synchronizer._detect_sync_issues(
            [(0, 0.02), (1, -0.03), (2, 0.05)], 0.03, 0.05, 0.95
        )
        
        assert len(good_issues) == 0
    
    def test_adjust_audio_speed(self):
        """测试音频速度调整"""
        mock_audio = Mock()
        mock_audio.speedup = Mock(return_value=mock_audio)
        mock_audio._spawn = Mock(return_value=mock_audio)
        mock_audio.set_frame_rate = Mock(return_value=mock_audio)
        mock_audio.frame_rate = 44100
        mock_audio.raw_data = b"test_data"
        
        # 测试加速
        result = self.synchronizer._adjust_audio_speed(mock_audio, 1.2)
        assert result is not None
        
        # 测试减速
        result = self.synchronizer._adjust_audio_speed(mock_audio, 0.8)
        assert result is not None
    
    @patch('services.audio_synchronizer.ffmpeg')
    def test_adjust_with_ffmpeg(self, mock_ffmpeg):
        """测试使用FFmpeg的音频调整"""
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
        
        with patch('services.audio_synchronizer.AudioSegment.from_wav', return_value=mock_audio):
            result = self.synchronizer._adjust_with_ffmpeg(mock_audio, 1.1)
            assert result is not None
    
    def test_verify_audio_quality_good(self):
        """测试良好音频质量验证"""
        original = Mock()
        original.__len__ = Mock(return_value=5000)
        
        adjusted = Mock()
        adjusted.__len__ = Mock(return_value=4500)  # 合理的时长变化
        adjusted.frame_rate = 44100  # 高采样率
        adjusted.dBFS = -20  # 合适的音量
        
        quality = self.synchronizer._verify_audio_quality(original, adjusted)
        assert quality is True
    
    def test_verify_audio_quality_poor(self):
        """测试较差音频质量验证"""
        original = Mock()
        original.__len__ = Mock(return_value=5000)
        
        adjusted = Mock()
        adjusted.__len__ = Mock(return_value=1000)  # 时长变化过大
        adjusted.frame_rate = 8000  # 低采样率
        adjusted.dBFS = -60  # 音量太小
        
        quality = self.synchronizer._verify_audio_quality(original, adjusted)
        assert quality is False
    
    def test_verify_audio_quality_exception(self):
        """测试音频质量验证异常处理"""
        original = Mock()
        adjusted = Mock()
        adjusted.frame_rate = Mock(side_effect=Exception("测试异常"))
        
        quality = self.synchronizer._verify_audio_quality(original, adjusted)
        assert quality is False
    
    def test_calculate_offset_distribution(self):
        """测试偏移分布计算"""
        segment_offsets = [
            (0, 0.05),   # excellent
            (1, 0.2),    # good
            (2, 0.4),    # fair
            (3, 0.8)     # poor
        ]
        
        distribution = self.synchronizer._calculate_offset_distribution(segment_offsets)
        
        assert distribution['excellent'] == 1
        assert distribution['good'] == 1
        assert distribution['fair'] == 1
        assert distribution['poor'] == 1
        assert sum(distribution.values()) == 4
    
    def test_generate_recommendations_poor_quality(self):
        """测试生成低质量的改进建议"""
        analysis_result = SyncAnalysisResult(
            timing_accuracy=0.3,
            avg_offset=0.8,
            max_offset=1.5,
            sync_quality_score=0.4,
            segment_offsets=[(0, 0.8), (1, -1.2), (2, 1.5)],
            issues_detected=["问题1", "问题2", "问题3"],
            processing_time=1.5
        )
        
        recommendations = self.synchronizer._generate_recommendations(analysis_result)
        
        assert len(recommendations) > 0
        assert any("重新进行语音合成" in rec for rec in recommendations)
        assert any("严重的时序偏移" in rec for rec in recommendations)
    
    def test_generate_recommendations_excellent_quality(self):
        """测试生成优秀质量的改进建议"""
        analysis_result = SyncAnalysisResult(
            timing_accuracy=0.98,
            avg_offset=0.02,
            max_offset=0.05,
            sync_quality_score=0.95,
            segment_offsets=[(0, 0.02), (1, -0.01), (2, 0.03)],
            issues_detected=[],
            processing_time=1.5
        )
        
        recommendations = self.synchronizer._generate_recommendations(analysis_result)
        
        assert len(recommendations) > 0
        assert any("同步质量优秀" in rec for rec in recommendations)
    
    @patch('services.audio_synchronizer.AudioSegment.from_file')
    def test_analyze_sync_quality_with_reference_segments(self, mock_from_file):
        """测试使用参考片段的同步质量分析"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)
        mock_from_file.return_value = mock_audio
        
        # 创建参考片段
        reference_segments = [
            TimedSegment(start_time=0.1, end_time=2.1, original_text="", translated_text=""),
            TimedSegment(start_time=2.1, end_time=4.1, original_text="", translated_text=""),
            TimedSegment(start_time=4.1, end_time=6.1, original_text="", translated_text="")
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = self.synchronizer.analyze_sync_quality(
                self.test_segments, temp_path, reference_segments
            )
            
            assert isinstance(result, SyncAnalysisResult)
            assert len(result.segment_offsets) == len(self.test_segments)
            
        finally:
            os.unlink(temp_path)
    
    @patch('services.audio_synchronizer.AudioSegment.from_file')
    def test_adjust_audio_timing_preserve_background(self, mock_from_file):
        """测试保留背景音的音频调整"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=8000)
        mock_audio.export = Mock()
        mock_from_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            input_path = temp_file.name
        
        # 模拟背景保留调整方法
        with patch.object(self.synchronizer, '_adjust_with_background_preservation', return_value=mock_audio):
            with patch.object(self.synchronizer, '_verify_audio_quality', return_value=True):
                try:
                    result = self.synchronizer.adjust_audio_timing(
                        input_path, self.test_segments, preserve_background=True
                    )
                    
                    assert isinstance(result, AudioAdjustmentResult)
                    assert result.background_preserved is True
                    
                finally:
                    os.unlink(input_path)