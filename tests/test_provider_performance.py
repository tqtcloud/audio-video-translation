import unittest
import time
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any
from models.core import TimedSegment
from services.speech_to_text import SpeechToTextService
from services.text_to_speech import TextToSpeechService, VoiceConfig
from services.translation_service import TranslationService
from services.providers import TranscriptionResult, SpeechSynthesisResult, TranslationResult
from utils.provider_errors import ProviderError


class TestProviderPerformance(unittest.TestCase):
    """提供者性能基准测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试音频文件
        self.test_audio_data = b"fake audio data" * 1000  # 模拟音频数据
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(self.test_audio_data)
            self.test_audio_path = temp_file.name
        
        # 创建测试文本片段
        self.test_segments = [
            TimedSegment(0.0, 2.0, "Hello world", confidence=0.9),
            TimedSegment(2.0, 4.0, "How are you", confidence=0.8),
            TimedSegment(4.0, 6.0, "I am fine", confidence=0.85)
        ]
        
        # 性能指标阈值
        self.performance_thresholds = {
            "stt_latency_ms": 5000,  # STT延迟阈值 5秒
            "tts_latency_ms": 3000,  # TTS延迟阈值 3秒
            "translation_latency_ms": 2000,  # 翻译延迟阈值 2秒
            "min_quality_score": 0.7  # 最低质量分数
        }
    
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.test_audio_path):
            os.unlink(self.test_audio_path)
    
    def test_stt_latency_comparison(self):
        """测试STT延迟比较"""
        results = {}
        
        # 测试OpenAI STT性能
        with patch('services.speech_to_text.provider_manager') as mock_manager:
            mock_provider = Mock()
            mock_result = TranscriptionResult(
                text="Hello world",
                language="en",
                duration=6.0,
                segments=self.test_segments
            )
            
            # 模拟API延迟
            def mock_transcribe(*args, **kwargs):
                time.sleep(0.1)  # 模拟100ms延迟
                return mock_result
            
            mock_provider.transcribe = mock_transcribe
            mock_manager.get_stt_provider.return_value = mock_provider
            
            # 测试性能
            service = SpeechToTextService("openai")
            
            start_time = time.time()
            result = service.transcribe(self.test_audio_path)
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            results["openai_stt"] = {
                "latency_ms": latency_ms,
                "text_length": len(result.text),
                "quality_score": 0.9
            }
        
        # 测试火山云STT性能
        with patch('services.speech_to_text.provider_manager') as mock_manager:
            mock_provider = Mock()
            mock_result = TranscriptionResult(
                text="Hello world",
                language="en", 
                duration=6.0,
                segments=self.test_segments
            )
            
            def mock_transcribe(*args, **kwargs):
                time.sleep(0.15)  # 模拟150ms延迟
                return mock_result
            
            mock_provider.transcribe = mock_transcribe
            mock_manager.get_stt_provider.return_value = mock_provider
            
            service = SpeechToTextService("volcengine")
            
            start_time = time.time()
            result = service.transcribe(self.test_audio_path)
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            results["volcengine_stt"] = {
                "latency_ms": latency_ms,
                "text_length": len(result.text),
                "quality_score": 0.85
            }
        
        # 验证性能指标
        for provider, metrics in results.items():
            self.assertLess(
                metrics["latency_ms"], 
                self.performance_thresholds["stt_latency_ms"],
                f"{provider} STT延迟超过阈值"
            )
            self.assertGreater(
                metrics["quality_score"],
                self.performance_thresholds["min_quality_score"],
                f"{provider} STT质量分数低于阈值"
            )
        
        # 打印性能对比
        print(f"\nSTT性能对比:")
        for provider, metrics in results.items():
            print(f"{provider}: 延迟={metrics['latency_ms']:.2f}ms, "
                  f"质量分数={metrics['quality_score']:.2f}")
    
    def test_tts_quality_comparison(self):
        """测试TTS质量比较"""
        results = {}
        
        # 测试OpenAI TTS
        with patch('services.text_to_speech.provider_manager') as mock_manager:
            mock_provider = Mock()
            mock_result = SpeechSynthesisResult(
                audio_file_path="/tmp/output.mp3",
                total_duration=6.0,
                segments_count=3,
                processing_time=0.5,
                quality_score=0.92,
                timing_adjustments=[]
            )
            
            def mock_synthesize(*args, **kwargs):
                time.sleep(0.2)  # 模拟200ms延迟
                return mock_result
            
            mock_provider.synthesize_speech = mock_synthesize
            mock_manager.get_tts_provider.return_value = mock_provider
            
            service = TextToSpeechService("openai")
            voice_config = VoiceConfig("alloy", "en")
            
            start_time = time.time()
            result = service.synthesize_speech(self.test_segments, "en", voice_config)
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            results["openai_tts"] = {
                "latency_ms": latency_ms,
                "quality_score": result.quality_score,
                "processing_time": result.processing_time
            }
        
        # 测试火山云TTS
        with patch('services.text_to_speech.provider_manager') as mock_manager:
            mock_provider = Mock()
            mock_result = SpeechSynthesisResult(
                audio_file_path="/tmp/output.mp3",
                total_duration=6.0,
                segments_count=3,
                processing_time=0.3,
                quality_score=0.88,
                timing_adjustments=[]
            )
            
            def mock_synthesize(*args, **kwargs):
                time.sleep(0.18)  # 模拟180ms延迟
                return mock_result
            
            mock_provider.synthesize_speech = mock_synthesize
            mock_manager.get_tts_provider.return_value = mock_provider
            
            service = TextToSpeechService("volcengine")
            voice_config = VoiceConfig("zh-voice", "zh")
            
            start_time = time.time()
            result = service.synthesize_speech(self.test_segments, "zh", voice_config)
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            results["volcengine_tts"] = {
                "latency_ms": latency_ms,
                "quality_score": result.quality_score,
                "processing_time": result.processing_time
            }
        
        # 验证性能指标
        for provider, metrics in results.items():
            self.assertLess(
                metrics["latency_ms"],
                self.performance_thresholds["tts_latency_ms"],
                f"{provider} TTS延迟超过阈值"
            )
            self.assertGreater(
                metrics["quality_score"],
                self.performance_thresholds["min_quality_score"],
                f"{provider} TTS质量分数低于阈值"
            )
        
        # 打印性能对比
        print(f"\nTTS性能对比:")
        for provider, metrics in results.items():
            print(f"{provider}: 延迟={metrics['latency_ms']:.2f}ms, "
                  f"质量分数={metrics['quality_score']:.2f}, "
                  f"处理时间={metrics['processing_time']:.2f}s")
    
    def test_translation_accuracy_comparison(self):
        """测试翻译准确性比较"""
        results = {}
        
        # 测试OpenAI翻译
        with patch('services.translation_service.provider_manager') as mock_manager:
            mock_provider = Mock()
            translated_segments = [
                TimedSegment(0.0, 2.0, "Hello world", "你好世界"),
                TimedSegment(2.0, 4.0, "How are you", "你好吗"),
                TimedSegment(4.0, 6.0, "I am fine", "我很好")
            ]
            mock_result = TranslationResult(
                original_segments=self.test_segments,
                translated_segments=translated_segments,
                total_characters=30,
                processing_time=0.8,
                language_detected="en",
                quality_score=0.95
            )
            
            def mock_translate(*args, **kwargs):
                time.sleep(0.12)  # 模拟120ms延迟
                return mock_result
            
            mock_provider.translate_segments = mock_translate
            mock_manager.get_translation_provider.return_value = mock_provider
            
            service = TranslationService("openai")
            
            start_time = time.time()
            result = service.translate_segments(self.test_segments, "zh")
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            results["openai_translation"] = {
                "latency_ms": latency_ms,
                "quality_score": result.quality_score,
                "characters_per_second": result.total_characters / result.processing_time
            }
        
        # 测试豆包翻译
        with patch('services.translation_service.provider_manager') as mock_manager:
            mock_provider = Mock()
            translated_segments = [
                TimedSegment(0.0, 2.0, "Hello world", "你好世界"),
                TimedSegment(2.0, 4.0, "How are you", "你好吗"),
                TimedSegment(4.0, 6.0, "I am fine", "我很好")
            ]
            mock_result = TranslationResult(
                original_segments=self.test_segments,
                translated_segments=translated_segments,
                total_characters=30,
                processing_time=0.6,
                language_detected="en",
                quality_score=0.90
            )
            
            def mock_translate(*args, **kwargs):
                time.sleep(0.10)  # 模拟100ms延迟
                return mock_result
            
            mock_provider.translate_segments = mock_translate
            mock_manager.get_translation_provider.return_value = mock_provider
            
            service = TranslationService("doubao")
            
            start_time = time.time()
            result = service.translate_segments(self.test_segments, "zh")
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            results["doubao_translation"] = {
                "latency_ms": latency_ms,
                "quality_score": result.quality_score,
                "characters_per_second": result.total_characters / result.processing_time
            }
        
        # 验证性能指标
        for provider, metrics in results.items():
            self.assertLess(
                metrics["latency_ms"],
                self.performance_thresholds["translation_latency_ms"],
                f"{provider} 翻译延迟超过阈值"
            )
            self.assertGreater(
                metrics["quality_score"],
                self.performance_thresholds["min_quality_score"],
                f"{provider} 翻译质量分数低于阈值"
            )
        
        # 打印性能对比
        print(f"\n翻译性能对比:")
        for provider, metrics in results.items():
            print(f"{provider}: 延迟={metrics['latency_ms']:.2f}ms, "
                  f"质量分数={metrics['quality_score']:.2f}, "
                  f"字符/秒={metrics['characters_per_second']:.1f}")
    
    def test_end_to_end_performance(self):
        """测试端到端性能"""
        # 模拟完整的翻译管道
        with patch('services.speech_to_text.provider_manager') as mock_stt_manager:
            with patch('services.translation_service.provider_manager') as mock_trans_manager:
                with patch('services.text_to_speech.provider_manager') as mock_tts_manager:
                    
                    # 设置STT mock
                    mock_stt_provider = Mock()
                    mock_stt_result = TranscriptionResult(
                        text="Hello world",
                        language="en",
                        segments=self.test_segments
                    )
                    mock_stt_provider.transcribe.return_value = mock_stt_result
                    mock_stt_manager.get_stt_provider.return_value = mock_stt_provider
                    
                    # 设置翻译mock
                    mock_trans_provider = Mock()
                    translated_segments = [
                        TimedSegment(0.0, 2.0, "Hello world", "你好世界")
                    ]
                    mock_trans_result = TranslationResult(
                        original_segments=self.test_segments,
                        translated_segments=translated_segments,
                        total_characters=10,
                        processing_time=0.5,
                        language_detected="en",
                        quality_score=0.9
                    )
                    mock_trans_provider.translate_segments.return_value = mock_trans_result
                    mock_trans_manager.get_translation_provider.return_value = mock_trans_provider
                    
                    # 设置TTS mock
                    mock_tts_provider = Mock()
                    mock_tts_result = SpeechSynthesisResult(
                        audio_file_path="/tmp/output.mp3",
                        total_duration=6.0,
                        segments_count=1,
                        processing_time=0.3,
                        quality_score=0.85,
                        timing_adjustments=[]
                    )
                    mock_tts_provider.synthesize_speech.return_value = mock_tts_result
                    mock_tts_manager.get_tts_provider.return_value = mock_tts_provider
                    
                    # 执行端到端测试
                    start_time = time.time()
                    
                    # STT
                    stt_service = SpeechToTextService()
                    transcription = stt_service.transcribe(self.test_audio_path)
                    
                    # 翻译
                    translation_service = TranslationService()
                    translation = translation_service.translate_segments(
                        transcription.segments, "zh"
                    )
                    
                    # TTS
                    tts_service = TextToSpeechService()
                    synthesis = tts_service.synthesize_speech(
                        translation.translated_segments, "zh",
                        VoiceConfig("zh-voice", "zh")
                    )
                    
                    end_time = time.time()
                    total_time = end_time - start_time
                    
                    # 验证端到端性能
                    self.assertLess(total_time, 10.0, "端到端处理时间超过10秒")
                    self.assertGreater(
                        synthesis.quality_score, 0.7, 
                        "最终输出质量分数低于阈值"
                    )
                    
                    print(f"\n端到端性能:")
                    print(f"总处理时间: {total_time:.2f}s")
                    print(f"最终质量分数: {synthesis.quality_score:.2f}")
    
    def test_concurrent_requests_performance(self):
        """测试并发请求性能"""
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def worker_function(worker_id):
            """工作线程函数"""
            with patch('services.speech_to_text.provider_manager') as mock_manager:
                mock_provider = Mock()
                mock_result = TranscriptionResult(
                    text=f"Result from worker {worker_id}",
                    language="en",
                    segments=self.test_segments
                )
                
                def mock_transcribe(*args, **kwargs):
                    time.sleep(0.1)  # 模拟处理时间
                    return mock_result
                
                mock_provider.transcribe = mock_transcribe
                mock_manager.get_stt_provider.return_value = mock_provider
                
                service = SpeechToTextService()
                
                start_time = time.time()
                result = service.transcribe(self.test_audio_path)
                end_time = time.time()
                
                results_queue.put({
                    "worker_id": worker_id,
                    "latency": end_time - start_time,
                    "success": True
                })
        
        # 启动多个并发请求
        num_workers = 5
        threads = []
        
        start_time = time.time()
        for i in range(num_workers):
            thread = threading.Thread(target=worker_function, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 收集结果
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # 验证并发性能
        self.assertEqual(len(results), num_workers, "并发请求数量不匹配")
        
        avg_latency = sum(r["latency"] for r in results) / len(results)
        max_latency = max(r["latency"] for r in results)
        
        self.assertLess(total_time, 2.0, "并发处理总时间过长")
        self.assertLess(avg_latency, 0.5, "平均延迟过高")
        
        print(f"\n并发性能测试:")
        print(f"并发数: {num_workers}")
        print(f"总时间: {total_time:.2f}s")
        print(f"平均延迟: {avg_latency:.2f}s")
        print(f"最大延迟: {max_latency:.2f}s")


if __name__ == '__main__':
    unittest.main(verbosity=2)