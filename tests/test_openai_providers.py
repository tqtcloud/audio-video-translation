import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from models.core import TimedSegment
from services.providers.openai_stt import OpenAISpeechToText
from services.providers.openai_tts import OpenAITextToSpeech
from services.providers.openai_translation import OpenAITranslation
from utils.provider_errors import ProviderError


class TestOpenAISpeechToText(unittest.TestCase):
    def setUp(self):
        self.stt = OpenAISpeechToText("test_api_key")
    
    def test_init_without_api_key(self):
        """测试没有API密钥时的初始化"""
        with self.assertRaises(ProviderError):
            OpenAISpeechToText(None)
    
    @patch('services.providers.openai_stt.OpenAI')
    def test_transcribe_success(self, mock_openai):
        """测试转录成功"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.text = "测试转录文本"
        mock_response.language = "zh"
        
        mock_client = Mock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # 创建临时音频文件
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(b"fake audio data")
            temp_path = temp_file.name
        
        try:
            result = self.stt.transcribe(temp_path, language="zh")
            
            self.assertEqual(result.text, "测试转录文本")
            self.assertEqual(result.language, "zh")
            
        finally:
            os.unlink(temp_path)
    
    @patch('services.providers.openai_stt.OpenAI')
    def test_transcribe_with_timestamps(self, mock_openai):
        """测试带时间戳的转录"""
        # 模拟API响应
        mock_segment = Mock()
        mock_segment.start = 0.0
        mock_segment.end = 2.5
        mock_segment.text = "测试片段"
        mock_segment.avg_logprob = 0.95
        
        mock_response = Mock()
        mock_response.text = "测试转录文本"
        mock_response.language = "zh"
        mock_response.duration = 10.5
        mock_response.segments = [mock_segment]
        
        mock_client = Mock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # 创建临时音频文件
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(b"fake audio data")
            temp_path = temp_file.name
        
        try:
            result = self.stt.transcribe_with_timestamps(temp_path)
            
            self.assertEqual(result.text, "测试转录文本")
            self.assertEqual(result.language, "zh")
            self.assertEqual(result.duration, 10.5)
            self.assertEqual(len(result.segments), 1)
            self.assertEqual(result.segments[0].start_time, 0.0)
            self.assertEqual(result.segments[0].end_time, 2.5)
            
        finally:
            os.unlink(temp_path)
    
    def test_validate_audio_file_unsupported_format(self):
        """测试不支持的文件格式"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            with self.assertRaises(ProviderError):
                self.stt._validate_audio_file(temp_path)
        finally:
            os.unlink(temp_path)


class TestOpenAITextToSpeech(unittest.TestCase):
    def setUp(self):
        self.tts = OpenAITextToSpeech("test_api_key")
    
    def test_init_without_api_key(self):
        """测试没有API密钥时的初始化"""
        with self.assertRaises(ProviderError):
            OpenAITextToSpeech(None)
    
    @patch('services.providers.openai_tts.openai')
    @patch('services.providers.openai_tts.AudioSegment')
    def test_synthesize_text_success(self, mock_audio_segment, mock_openai):
        """测试文本合成成功"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.content = b"fake audio data"
        
        mock_openai.audio.speech.create.return_value = mock_response
        
        result_path = self.tts.synthesize_text("测试文本", "zh")
        
        self.assertTrue(result_path.endswith('.mp3'))
        self.assertTrue(os.path.exists(result_path))
        
        # 清理临时文件
        if os.path.exists(result_path):
            os.unlink(result_path)
    
    def test_synthesize_speech_empty_segments(self):
        """测试空片段列表"""
        with self.assertRaises(ProviderError):
            self.tts.synthesize_speech([], "zh")
    
    def test_synthesize_speech_unsupported_language(self):
        """测试不支持的语言"""
        segments = [TimedSegment(0.0, 2.0, "test", translated_text="测试")]
        
        with self.assertRaises(ProviderError):
            self.tts.synthesize_speech(segments, "unknown")


class TestOpenAITranslation(unittest.TestCase):
    def setUp(self):
        self.translator = OpenAITranslation("test_api_key")
    
    def test_init_without_api_key(self):
        """测试没有API密钥时的初始化"""
        with self.assertRaises(ProviderError):
            OpenAITranslation(None)
    
    def test_translate_text_same_language(self):
        """测试相同语言翻译"""
        result = self.translator.translate_text("Hello world", "en", "en")
        self.assertEqual(result, "Hello world")
    
    def test_translate_segments_empty_list(self):
        """测试空片段列表"""
        with self.assertRaises(ProviderError):
            self.translator.translate_segments([], "zh")
    
    def test_translate_segments_unsupported_language(self):
        """测试不支持的语言"""
        segments = [TimedSegment(0.0, 2.0, "Hello")]
        
        with self.assertRaises(ProviderError):
            self.translator.translate_segments(segments, "unknown")
    
    @patch('services.providers.openai_translation.openai')
    def test_translate_segments_same_language(self, mock_openai):
        """测试相同语言的片段翻译"""
        segments = [
            TimedSegment(0.0, 2.0, "Hello"),
            TimedSegment(2.0, 4.0, "World")
        ]
        
        result = self.translator.translate_segments(segments, "en", "en")
        
        self.assertEqual(len(result.translated_segments), 2)
        self.assertEqual(result.translated_segments[0].translated_text, "Hello")
        self.assertEqual(result.translated_segments[1].translated_text, "World")
        self.assertEqual(result.quality_score, 1.0)
    
    def test_detect_text_language_chinese(self):
        """测试中文语言检测"""
        chinese_text = "这是一段中文文本"
        result = self.translator._detect_text_language(chinese_text)
        self.assertEqual(result, "zh")
    
    def test_detect_text_language_english(self):
        """测试英文语言检测"""
        english_text = "This is an English text with common words like the and is"
        result = self.translator._detect_text_language(english_text)
        self.assertEqual(result, "en")
    
    def test_batch_segments(self):
        """测试片段分批"""
        # 创建大量短片段
        segments = [TimedSegment(i, i+1, "a" * 100) for i in range(50)]
        
        batches = self.translator._batch_segments(segments)
        
        # 验证分批结果
        self.assertGreater(len(batches), 1)  # 应该被分成多批
        
        # 验证每批的大小不超过限制
        for batch in batches:
            total_length = sum(len(seg.original_text) for seg in batch)
            self.assertLessEqual(total_length, self.translator.max_tokens_per_request)


if __name__ == '__main__':
    unittest.main()