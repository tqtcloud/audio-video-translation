import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import json
from models.core import TimedSegment
from services.providers.volcengine_stt import VolcengineSpeechToText
from services.providers.volcengine_tts import VolcengineTextToSpeech
from services.providers.doubao_translation import DoubaoTranslation
from utils.provider_errors import ProviderError


class TestVolcengineSpeechToText(unittest.TestCase):
    def setUp(self):
        self.stt = VolcengineSpeechToText("test_app_id", "test_token", "test_cluster")
    
    def test_init_without_params(self):
        """测试缺少参数时的初始化"""
        with self.assertRaises(ProviderError):
            VolcengineSpeechToText("", "test_token")
        
        with self.assertRaises(ProviderError):
            VolcengineSpeechToText("test_app_id", "")
    
    def test_validate_audio_file_unsupported_format(self):
        """测试不支持的文件格式"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            with self.assertRaises(ProviderError):
                self.stt._validate_audio_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validate_audio_file_empty(self):
        """测试空文件"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            with self.assertRaises(ProviderError):
                self.stt._validate_audio_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_build_websocket_url(self):
        """测试WebSocket URL构建"""
        url = self.stt._build_websocket_url()
        
        self.assertIn("test_app_id", url)
        self.assertIn("test_token", url)
        self.assertIn("test_cluster", url)
        self.assertTrue(url.startswith("wss://"))
    
    def test_detect_language_fallback(self):
        """测试语言检测回退"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(b"fake audio data")
            temp_path = temp_file.name
        
        try:
            # 模拟转录失败，应该返回默认语言
            with patch.object(self.stt, 'transcribe', side_effect=Exception("Mock error")):
                result = self.stt.detect_language(temp_path)
                self.assertEqual(result, 'zh')
        finally:
            os.unlink(temp_path)


class TestVolcengineTextToSpeech(unittest.TestCase):
    def setUp(self):
        self.tts = VolcengineTextToSpeech("test_app_id", "test_token")
    
    def test_init_without_params(self):
        """测试缺少参数时的初始化"""
        with self.assertRaises(ProviderError):
            VolcengineTextToSpeech("", "test_token")
        
        with self.assertRaises(ProviderError):
            VolcengineTextToSpeech("test_app_id", "")
    
    def test_synthesize_speech_empty_segments(self):
        """测试空片段列表"""
        with self.assertRaises(ProviderError):
            self.tts.synthesize_speech([], "zh")
    
    def test_synthesize_text_empty(self):
        """测试空文本"""
        with self.assertRaises(ProviderError):
            self.tts.synthesize_text("", "zh")
    
    @patch('services.providers.volcengine_tts.requests.post')
    def test_call_tts_api_single_success(self, mock_post):
        """测试TTS API调用成功"""
        # 模拟成功响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "success",
            "data": {
                "audio": "ZmFrZSBhdWRpbyBkYXRh"  # base64 encoded "fake audio data"
            }
        }
        mock_post.return_value = mock_response
        
        result = self.tts._call_tts_api_single("测试文本", "zh", {"voice_id": "test_voice"})
        
        self.assertEqual(result, b"fake audio data")
        mock_post.assert_called_once()
    
    @patch('services.providers.volcengine_tts.requests.post')
    def test_call_tts_api_single_error(self, mock_post):
        """测试TTS API调用错误"""
        # 模拟错误响应
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        with self.assertRaises(ProviderError):
            self.tts._call_tts_api_single("测试文本", "zh", {"voice_id": "test_voice"})
    
    def test_split_text_into_chunks(self):
        """测试文本分块"""
        # 创建长文本
        long_text = "这是第一句。" * 200 + "这是第二句。" * 200
        
        chunks = self.tts._split_text_into_chunks(long_text)
        
        # 验证分块结果
        self.assertGreater(len(chunks), 1)
        
        # 验证每块的大小不超过限制
        for chunk in chunks:
            self.assertLessEqual(len(chunk), self.tts.max_text_length)


class TestDoubaoTranslation(unittest.TestCase):
    def setUp(self):
        self.translator = DoubaoTranslation("test_api_key", "https://test.api.com", "test-model")
    
    def test_init_without_params(self):
        """测试缺少参数时的初始化"""
        with self.assertRaises(ProviderError):
            DoubaoTranslation("", "https://test.api.com", "test-model")
        
        with self.assertRaises(ProviderError):
            DoubaoTranslation("test_api_key", "", "test-model")
        
        with self.assertRaises(ProviderError):
            DoubaoTranslation("test_api_key", "https://test.api.com", "")
    
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
    
    def test_translate_segments_same_language(self):
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
    
    @patch('services.providers.doubao_translation.requests.post')
    def test_call_doubao_api_success(self, mock_post):
        """测试豆包API调用成功"""
        # 模拟成功响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "翻译结果"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        request_data = {"model": "test-model", "messages": []}
        result = self.translator._call_doubao_api_with_retry(request_data)
        
        self.assertEqual(result, "翻译结果")
        mock_post.assert_called_once()
    
    @patch('services.providers.doubao_translation.requests.post')
    def test_call_doubao_api_auth_error(self, mock_post):
        """测试豆包API认证错误"""
        # 模拟认证错误
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        request_data = {"model": "test-model", "messages": []}
        
        with self.assertRaises(ProviderError) as context:
            self.translator._call_doubao_api_with_retry(request_data)
        
        self.assertIn("认证失败", str(context.exception))
    
    @patch('services.providers.doubao_translation.requests.post')
    def test_call_doubao_api_rate_limit(self, mock_post):
        """测试豆包API频率限制"""
        # 模拟频率限制错误
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response
        
        request_data = {"model": "test-model", "messages": []}
        
        with self.assertRaises(ProviderError) as context:
            self.translator._call_doubao_api_with_retry(request_data)
        
        self.assertIn("频率超限", str(context.exception))
    
    def test_batch_segments(self):
        """测试片段分批"""
        # 创建大量短片段
        segments = [TimedSegment(i, i+1, "a" * 100) for i in range(50)]
        
        batches = self.translator._batch_segments(segments)
        
        # 验证分批结果
        self.assertGreater(len(batches), 1)
        
        # 验证每批的大小不超过限制
        for batch in batches:
            total_length = sum(len(seg.original_text) for seg in batch)
            self.assertLessEqual(total_length, self.translator.max_tokens_per_request)


if __name__ == '__main__':
    unittest.main()