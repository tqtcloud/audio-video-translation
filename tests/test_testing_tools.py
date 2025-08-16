#!/usr/bin/env python3
"""
测试工具的单元测试
验证测试数据生成器和质量评估工具的功能
"""

import pytest
import tempfile
import os
import json
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from tests.test_data_generator import TestDataGenerator, TestDataSpec
from tests.quality_metrics import (
    QualityAssessmentTool, 
    AudioQualityMetrics, 
    VideoQualityMetrics,
    TranslationQualityMetrics,
    SyncQualityMetrics
)


class TestTestDataGenerator:
    """测试数据生成器的测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.generator = TestDataGenerator(self.temp_dir)
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass
    
    def test_init(self):
        """测试初始化"""
        assert self.generator.output_dir.exists()
        assert len(self.generator.test_texts) > 0
        assert "en" in self.generator.test_texts
        assert "zh-CN" in self.generator.test_texts
    
    def test_audio_spec_creation(self):
        """测试音频规格创建"""
        spec = TestDataSpec(
            file_type="audio",
            format="mp3",
            duration=10.0,
            sample_rate=44100,
            channels=2,
            content_type="speech",
            language="en"
        )
        
        assert spec.file_type == "audio"
        assert spec.format == "mp3"
        assert spec.duration == 10.0
        assert spec.sample_rate == 44100
        assert spec.channels == 2
        assert spec.content_type == "speech"
        assert spec.language == "en"
    
    def test_video_spec_creation(self):
        """测试视频规格创建"""
        spec = TestDataSpec(
            file_type="video",
            format="mp4",
            duration=15.0,
            video_resolution="1280x720",
            video_fps=30,
            content_type="speech",
            language="en"
        )
        
        assert spec.file_type == "video"
        assert spec.format == "mp4"
        assert spec.duration == 15.0
        assert spec.video_resolution == "1280x720"
        assert spec.video_fps == 30
    
    @patch('tests.test_data_generator.subprocess.run')
    def test_generate_tone_audio(self, mock_subprocess):
        """测试生成音调音频"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        spec = TestDataSpec(
            file_type="audio",
            format="wav",
            duration=5.0,
            content_type="speech"
        )
        
        output_path = self.temp_dir + "/test_tone.wav"
        
        # 测试内部方法（通常不推荐，但这里用于验证逻辑）
        self.generator._generate_tone_audio(spec, output_path)
        
        # 验证 ffmpeg 被调用
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in call_args
        assert "sine" in " ".join(call_args)
    
    @patch('tests.test_data_generator.subprocess.run')
    def test_generate_silence_audio(self, mock_subprocess):
        """测试生成静音音频"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        spec = TestDataSpec(
            file_type="audio",
            format="wav",
            duration=3.0,
            content_type="silence"
        )
        
        output_path = Path(self.temp_dir) / "test_silence.wav"
        
        with patch.object(self.generator, '_convert_audio_format') as mock_convert:
            mock_convert.return_value = str(output_path)
            
            result = self.generator._generate_silence_audio(spec, output_path)
            
            assert result == str(output_path)
            mock_subprocess.assert_called_once()
    
    def test_generate_test_dataset_structure(self):
        """测试生成测试数据集的结构"""
        specs = [
            TestDataSpec(file_type="audio", format="mp3", duration=5.0, content_type="speech"),
            TestDataSpec(file_type="audio", format="wav", duration=5.0, content_type="music")
        ]
        
        with patch.object(self.generator, '_generate_audio_file') as mock_gen_audio:
            mock_gen_audio.side_effect = ["/path/file1.mp3", "/path/file2.wav"]
            
            result = self.generator.generate_test_dataset(specs)
            
            assert len(result) == 2
            assert "test_audio_mp3_001.mp3" in result
            assert "test_audio_wav_002.wav" in result
            
            # 验证数据集信息文件
            info_file = self.generator.output_dir / "dataset_info.json"
            assert info_file.exists()
            
            with open(info_file, 'r') as f:
                info = json.load(f)
            
            assert info["total_files"] == 2
            assert "generated_at" in info
            assert "specs" in info
    
    def test_clean_test_data(self):
        """测试清理测试数据"""
        # 创建一些测试文件
        test_file = self.generator.output_dir / "test.txt"
        test_file.write_text("test content")
        
        assert test_file.exists()
        
        self.generator.clean_test_data()
        
        assert not self.generator.output_dir.exists()


class TestQualityAssessmentTool:
    """质量评估工具的测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.tool = QualityAssessmentTool()
    
    def teardown_method(self):
        """清理测试环境"""
        # 清理临时目录
        import shutil
        try:
            shutil.rmtree(self.tool.temp_dir)
        except:
            pass
    
    def test_init(self):
        """测试初始化"""
        assert self.tool.temp_dir.exists()
    
    @patch('tests.quality_metrics.librosa.load')
    def test_calculate_snr(self, mock_librosa_load):
        """测试信噪比计算"""
        # 模拟音频数据
        signal = np.array([1.0, 0.5, -0.5, -1.0])
        noisy_signal = signal + np.array([0.1, -0.1, 0.1, -0.1])
        
        snr = self.tool._calculate_snr(signal, noisy_signal)
        
        assert isinstance(snr, float)
        assert snr > 0  # 应该有正的信噪比
    
    def test_calculate_dynamic_range(self):
        """测试动态范围计算"""
        # 创建测试信号：大部分为小值，少数为大值
        signal = np.concatenate([
            np.full(90, 0.01),  # 90% 小值（噪声底限）
            np.full(10, 1.0)    # 10% 大值（峰值）
        ])
        
        dynamic_range = self.tool._calculate_dynamic_range(signal)
        
        assert isinstance(dynamic_range, float)
        assert dynamic_range > 0
    
    def test_calculate_thd_simple(self):
        """测试总谐波失真计算（简化版）"""
        # 创建纯正弦波
        sample_rate = 44100
        duration = 0.1
        frequency = 440
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * frequency * t)
        
        thd = self.tool._calculate_thd(signal, sample_rate)
        
        assert isinstance(thd, float)
        assert thd >= 0
    
    def test_analyze_frequency_response(self):
        """测试频率响应分析"""
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # 原始信号：多频率成分
        original = (np.sin(2 * np.pi * 100 * t) +   # 低频
                   np.sin(2 * np.pi * 1000 * t) +   # 中频
                   np.sin(2 * np.pi * 5000 * t))    # 高频
        
        # 处理后信号：略有变化
        processed = original * 0.9
        
        response = self.tool._analyze_frequency_response(original, processed, sample_rate)
        
        assert isinstance(response, dict)
        assert "low_band_ratio" in response
        assert "mid_band_ratio" in response
        assert "high_band_ratio" in response
        
        # 所有比值应该接近0.9^2 = 0.81（功率比）
        for ratio in response.values():
            assert 0.5 < ratio < 1.5  # 合理范围
    
    @patch('tests.quality_metrics.subprocess.run')
    def test_get_video_info(self, mock_subprocess):
        """测试获取视频信息"""
        # 模拟 ffprobe 输出
        mock_result = Mock()
        mock_result.stdout = json.dumps({
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                    "bit_rate": "2000000"
                }
            ]
        })
        mock_subprocess.return_value = mock_result
        
        info = self.tool._get_video_info("/test/video.mp4")
        
        assert info["codec_name"] == "h264"
        assert info["width"] == 1920
        assert info["height"] == 1080
        mock_subprocess.assert_called_once()
    
    def test_calculate_bleu_score(self):
        """测试BLEU分数计算"""
        reference = "The quick brown fox jumps over the lazy dog"
        candidate = "The fast brown fox jumps over the lazy dog"
        
        bleu = self.tool._calculate_bleu_score(reference, candidate)
        
        assert isinstance(bleu, float)
        assert 0 <= bleu <= 1
        assert bleu > 0.5  # 应该有较高的相似性
    
    def test_calculate_ter_score(self):
        """测试TER分数计算"""
        reference = "hello world test"
        candidate = "hello world testing"
        
        ter = self.tool._calculate_ter_score(reference, candidate)
        
        assert isinstance(ter, float)
        assert ter >= 0
        # TER应该相对较低，因为只有一个词不同
        assert ter < 1.0
    
    def test_get_ngrams(self):
        """测试n-gram提取"""
        tokens = ["the", "quick", "brown", "fox"]
        
        # 测试2-gram
        bigrams = self.tool._get_ngrams(tokens, 2)
        expected_bigrams = {
            ("the", "quick"): 1,
            ("quick", "brown"): 1,
            ("brown", "fox"): 1
        }
        
        assert bigrams == expected_bigrams
        
        # 测试3-gram
        trigrams = self.tool._get_ngrams(tokens, 3)
        assert len(trigrams) == 2  # 3个3-gram
    
    def test_calculate_word_accuracy(self):
        """测试词准确率计算"""
        reference = "the quick brown fox"
        candidate = "the fast brown fox"
        
        accuracy = self.tool._calculate_word_accuracy(reference, candidate)
        
        assert isinstance(accuracy, float)
        assert 0 <= accuracy <= 1
        assert accuracy == 0.75  # 4个词中3个正确
    
    def test_calculate_sentence_accuracy(self):
        """测试句子准确率计算"""
        reference = "Hello world. How are you."
        candidate = "Hello world. How are you today."
        
        accuracy = self.tool._calculate_sentence_accuracy(reference, candidate)
        
        assert isinstance(accuracy, float)
        assert 0 <= accuracy <= 1
    
    def test_calculate_fluency_score_english(self):
        """测试英语流畅度分数计算"""
        # 简单、流畅的文本
        text = "This is a simple and clear sentence."
        
        score = self.tool._calculate_fluency_score(text, "en")
        
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_calculate_adequacy_score(self):
        """测试充分性分数计算"""
        reference = "The implementation includes audio processing and translation"
        candidate = "The implementation includes audio processing"
        
        score = self.tool._calculate_adequacy_score(reference, candidate)
        
        assert isinstance(score, float)
        assert 0 <= score <= 1
        assert score > 0  # 应该有一些内容覆盖
    
    def test_calculate_timing_accuracy(self):
        """测试时序准确性计算"""
        original_segments = [
            {"start": 0.0, "end": 5.0, "text": "hello"},
            {"start": 5.0, "end": 10.0, "text": "world"}
        ]
        
        translated_segments = [
            {"start": 0.0, "end": 4.8, "text": "你好"},
            {"start": 5.0, "end": 9.5, "text": "世界"}
        ]
        
        accuracy = self.tool._calculate_timing_accuracy(original_segments, translated_segments)
        
        assert isinstance(accuracy, float)
        assert 0 <= accuracy <= 1
        assert accuracy > 0.8  # 时序差异较小
    
    def test_calculate_segment_alignment(self):
        """测试段落对齐度计算"""
        original_segments = [
            {"start": 0.0, "end": 5.0, "text": "hello"},
            {"start": 5.0, "end": 10.0, "text": "world"}
        ]
        
        translated_segments = [
            {"start": 0.1, "end": 5.1, "text": "你好"},
            {"start": 5.1, "end": 10.1, "text": "世界"}
        ]
        
        alignment = self.tool._calculate_segment_alignment(original_segments, translated_segments)
        
        assert isinstance(alignment, float)
        assert 0 <= alignment <= 1
        assert alignment > 0.9  # 对齐度应该很高
    
    @patch('tests.quality_metrics.librosa.load')
    @patch('tests.quality_metrics.librosa.stft')
    def test_calculate_lip_sync_score(self, mock_stft, mock_load):
        """测试唇形同步分数计算"""
        # 模拟音频数据
        mock_load.side_effect = [
            (np.random.random(44100), 44100),  # 原始音频
            (np.random.random(44100), 44100)   # 翻译音频
        ]
        
        # 模拟STFT结果
        mock_stft.side_effect = [
            np.random.random((1025, 100)) + 1j * np.random.random((1025, 100)),
            np.random.random((1025, 100)) + 1j * np.random.random((1025, 100))
        ]
        
        score = self.tool._calculate_lip_sync_score("/test/orig.wav", "/test/trans.wav")
        
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_calculate_overall_quality_score(self):
        """测试总体质量分数计算"""
        metrics = {
            "audio_quality": {
                "snr_db": 30.0,
                "dynamic_range": 50.0,
                "duration_accuracy": 0.95,
                "thd": 0.05
            },
            "video_quality": {
                "psnr": 35.0,
                "ssim": 0.9,
                "sync_offset": 0.1
            },
            "translation_quality": {
                "bleu_score": 0.8,
                "word_accuracy": 0.85,
                "fluency_score": 0.9,
                "adequacy_score": 0.88
            },
            "sync_quality": {
                "overall_sync_score": 0.85
            }
        }
        
        score = self.tool._calculate_overall_quality_score(metrics)
        
        assert isinstance(score, float)
        assert 0 <= score <= 1
        assert score > 0.5  # 应该有较高的总体质量
    
    def test_audio_quality_metrics_dataclass(self):
        """测试音频质量指标数据类"""
        metrics = AudioQualityMetrics(
            snr_db=25.0,
            thd=0.05,
            dynamic_range=45.0,
            duration_accuracy=0.98
        )
        
        assert metrics.snr_db == 25.0
        assert metrics.thd == 0.05
        assert metrics.dynamic_range == 45.0
        assert metrics.duration_accuracy == 0.98
    
    def test_video_quality_metrics_dataclass(self):
        """测试视频质量指标数据类"""
        metrics = VideoQualityMetrics(
            psnr=30.0,
            ssim=0.9,
            bitrate=2000000,
            frame_rate=30.0,
            resolution="1920x1080"
        )
        
        assert metrics.psnr == 30.0
        assert metrics.ssim == 0.9
        assert metrics.bitrate == 2000000
        assert metrics.frame_rate == 30.0
        assert metrics.resolution == "1920x1080"
    
    def test_translation_quality_metrics_dataclass(self):
        """测试翻译质量指标数据类"""
        metrics = TranslationQualityMetrics(
            bleu_score=0.75,
            meteor_score=0.8,
            ter_score=0.2,
            length_ratio=1.1,
            word_accuracy=0.85
        )
        
        assert metrics.bleu_score == 0.75
        assert metrics.meteor_score == 0.8
        assert metrics.ter_score == 0.2
        assert metrics.length_ratio == 1.1
        assert metrics.word_accuracy == 0.85
    
    def test_sync_quality_metrics_dataclass(self):
        """测试同步质量指标数据类"""
        metrics = SyncQualityMetrics(
            timing_accuracy=0.9,
            lip_sync_score=0.8,
            segment_alignment=0.95,
            overall_sync_score=0.88
        )
        
        assert metrics.timing_accuracy == 0.9
        assert metrics.lip_sync_score == 0.8
        assert metrics.segment_alignment == 0.95
        assert metrics.overall_sync_score == 0.88
    
    def test_generate_quality_report_structure(self):
        """测试质量报告生成的结构"""
        processing_results = {
            "audio_extraction": {"audio_path": "/test/audio.wav"},
            "audio_sync": {"final_audio_path": "/test/final.wav"},
            "speech_to_text": {"transcription": "hello world", "segments": []},
            "text_translation": {"translated_segments": []}
        }
        
        # 模拟质量评估方法
        with patch.object(self.tool, 'assess_audio_quality') as mock_audio, \
             patch.object(self.tool, 'assess_video_quality') as mock_video, \
             patch.object(self.tool, 'assess_sync_quality') as mock_sync:
            
            mock_audio.return_value = AudioQualityMetrics(snr_db=25.0)
            mock_video.return_value = VideoQualityMetrics(psnr=30.0)
            mock_sync.return_value = SyncQualityMetrics(timing_accuracy=0.9)
            
            report = self.tool.generate_quality_report(
                "test_job", "/test/input.mp4", "/test/output.mp4", processing_results
            )
            
            assert "job_id" in report
            assert "timestamp" in report
            assert "files" in report
            assert "metrics" in report
            assert report["job_id"] == "test_job"
    
    def test_save_quality_report(self):
        """测试保存质量报告"""
        report = {
            "job_id": "test_001",
            "metrics": {"overall_score": 0.85}
        }
        
        output_file = os.path.join(self.tool.temp_dir, "test_report.json")
        
        self.tool.save_quality_report(report, output_file)
        
        assert os.path.exists(output_file)
        
        with open(output_file, 'r') as f:
            loaded_report = json.load(f)
        
        assert loaded_report["job_id"] == "test_001"
        assert loaded_report["metrics"]["overall_score"] == 0.85


class TestIntegrationBetweenTools:
    """测试工具之间的集成"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass
    
    @patch('tests.test_data_generator.subprocess.run')
    def test_generator_and_quality_tool_integration(self, mock_subprocess):
        """测试数据生成器和质量工具的集成"""
        # 设置模拟
        mock_subprocess.return_value = Mock(returncode=0)
        
        # 创建生成器和质量工具
        generator = TestDataGenerator(self.temp_dir)
        quality_tool = QualityAssessmentTool()
        
        # 生成测试数据
        specs = [TestDataSpec(file_type="audio", format="mp3", duration=5.0)]
        
        with patch.object(generator, '_convert_audio_format') as mock_convert:
            # 创建实际的测试文件
            test_file = os.path.join(self.temp_dir, "test_audio.mp3")
            with open(test_file, 'wb') as f:
                f.write(b"fake audio data")
            
            mock_convert.return_value = test_file
            
            generated_files = generator.generate_test_dataset(specs)
            
            assert len(generated_files) > 0
            
            # 验证文件存在
            first_file = list(generated_files.values())[0]
            assert os.path.exists(first_file)
            
            # 使用质量工具评估（模拟）
            with patch.object(quality_tool, 'assess_audio_quality') as mock_assess:
                mock_assess.return_value = AudioQualityMetrics(snr_db=20.0)
                
                metrics = quality_tool.assess_audio_quality(first_file, first_file)
                
                assert isinstance(metrics, AudioQualityMetrics)
                assert metrics.snr_db == 20.0
    
    def test_error_handling_in_tools(self):
        """测试工具的错误处理"""
        generator = TestDataGenerator(self.temp_dir)
        quality_tool = QualityAssessmentTool()
        
        # 测试不存在的文件
        with patch('tests.quality_metrics.librosa.load', side_effect=Exception("文件加载失败")):
            metrics = quality_tool.assess_audio_quality("/nonexistent.wav", "/nonexistent2.wav")
            
            # 应该返回默认的指标对象
            assert isinstance(metrics, AudioQualityMetrics)
            assert metrics.snr_db == 0.0  # 默认值
    
    def test_data_consistency_between_tools(self):
        """测试工具间数据一致性"""
        # 测试相同输入产生一致的结果
        generator = TestDataGenerator(self.temp_dir)
        
        spec1 = TestDataSpec(file_type="audio", format="mp3", duration=10.0)
        spec2 = TestDataSpec(file_type="audio", format="mp3", duration=10.0)
        
        # 规格应该是相等的
        assert spec1.file_type == spec2.file_type
        assert spec1.format == spec2.format
        assert spec1.duration == spec2.duration
        
        # 测试文本选择的一致性
        texts1 = generator.test_texts["en"]
        texts2 = generator.test_texts["en"]
        
        assert texts1 == texts2  # 应该完全相同


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])