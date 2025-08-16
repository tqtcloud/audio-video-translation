import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock, mock_open
from services.speech_to_text import SpeechToTextService, SpeechToTextError
from services.providers import TranscriptionResult
from models.core import TimedSegment


class TestTranscriptionResult:
    
    def test_init_basic(self):
        """测试基本初始化"""
        result = TranscriptionResult("Hello world")
        
        assert result.text == "Hello world"
        assert result.language is None
        assert result.duration is None
        assert result.segments == []
    
    def test_init_with_all_params(self):
        """测试完整参数初始化"""
        segments = [
            TimedSegment(start_time=0.0, end_time=2.0, original_text="Hello", confidence=0.9)
        ]
        
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            duration=10.5,
            segments=segments
        )
        
        assert result.text == "Hello world"
        assert result.language == "en"
        assert result.duration == 10.5
        assert len(result.segments) == 1
        assert result.segments[0].original_text == "Hello"


class TestSpeechToTextService:
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_audio_path = os.path.join(self.temp_dir, "test.wav")
        
        # 创建模拟音频文件
        with open(self.mock_audio_path, 'wb') as f:
            f.write(b"mock audio content")
        
        # 模拟配置和提供者
        with patch('services.speech_to_text.provider_manager') as mock_manager:
            mock_provider = MagicMock()
            mock_manager.get_stt_provider.return_value = mock_provider
            self.service = SpeechToTextService()
            self.mock_provider = mock_provider
    
    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_init_with_provider_type(self):
        """测试使用指定提供者类型初始化"""
        with patch('services.speech_to_text.provider_manager') as mock_manager:
            mock_provider = MagicMock()
            mock_manager.get_stt_provider.return_value = mock_provider
            service = SpeechToTextService(provider_type="volcengine")
            assert service.provider == mock_provider
    
    def test_init_provider_error(self):
        """测试提供者初始化错误"""
        with patch('services.speech_to_text.provider_manager') as mock_manager:
            from utils.provider_errors import ProviderError
            mock_manager.get_stt_provider.side_effect = ProviderError("初始化失败")
            with pytest.raises(SpeechToTextError, match="初始化语音转文字提供者失败"):
                SpeechToTextService()
    
    def test_supported_formats(self):
        """测试支持的文件格式"""
        # 这个测试现在需要委托给提供者
        self.mock_provider.get_supported_formats.return_value = ['.mp3', '.wav']
        if hasattr(self.service.provider, 'get_supported_formats'):
            formats = self.service.provider.get_supported_formats()
            assert '.mp3' in formats
    
    def test_transcribe_success(self):
        """测试转录成功"""
        # 模拟提供者响应
        mock_result = TranscriptionResult(
            text="Hello, this is a test transcription.",
            language="en",
            segments=[TimedSegment(0.0, 2.0, "Hello, this is a test transcription.")]
        )
        self.mock_provider.transcribe.return_value = mock_result
        
        result = self.service.transcribe(self.mock_audio_path)
        
        assert isinstance(result, TranscriptionResult)
        assert result.text == "Hello, this is a test transcription."
        assert result.language == "en"
        
        # 验证提供者被调用
        self.mock_provider.transcribe.assert_called_once_with(self.mock_audio_path, None, None)
    
    def test_transcribe_file_not_exists(self):
        """测试文件不存在的情况"""
        non_existent_path = "/path/to/nonexistent.wav"
        
        # 模拟提供者抛出错误
        from utils.provider_errors import ProviderError
        self.mock_provider.transcribe.side_effect = ProviderError("文件不存在")
        
        with pytest.raises(SpeechToTextError, match="转录失败"):
            self.service.transcribe(non_existent_path)
    
    def test_transcribe_unsupported_format(self):
        """测试不支持的文件格式"""
        unsupported_file = os.path.join(self.temp_dir, "test.txt")
        with open(unsupported_file, 'w') as f:
            f.write("text file")
        
        # 模拟提供者抛出错误
        from utils.provider_errors import ProviderError
        self.mock_provider.transcribe.side_effect = ProviderError("不支持的格式")
        
        with pytest.raises(SpeechToTextError, match="转录失败"):
            self.service.transcribe(unsupported_file)
    
    def test_transcribe_file_too_large(self):
        """测试文件太大的情况"""
        large_file = os.path.join(self.temp_dir, "large.wav")
        
        # 模拟大文件
        with patch('os.path.getsize', return_value=30 * 1024 * 1024):  # 30MB
            with open(large_file, 'w') as f:
                f.write("content")
            
            with pytest.raises(SpeechToTextError, match="文件太大"):
                self.service.transcribe(large_file)
    
    @patch('services.speech_to_text.OpenAI')
    def test_transcribe_with_language(self, mock_openai):
        """测试指定语言的转录"""
        mock_response = MagicMock()
        mock_response.text = "你好，这是一个测试。"
        mock_response.language = "zh"
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        service = SpeechToTextService(api_key="test_key")
        result = service.transcribe(self.mock_audio_path, language="zh")
        
        # 验证API调用参数
        call_args = mock_client.audio.transcriptions.create.call_args
        assert call_args[1]["language"] == "zh"
        assert result.text == "你好，这是一个测试。"
    
    @patch('services.speech_to_text.OpenAI')
    def test_transcribe_with_prompt(self, mock_openai):
        """测试使用提示的转录"""
        mock_response = MagicMock()
        mock_response.text = "Technical discussion about AI."
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        service = SpeechToTextService(api_key="test_key")
        prompt = "This is a technical discussion"
        result = service.transcribe(self.mock_audio_path, prompt=prompt)
        
        # 验证API调用参数
        call_args = mock_client.audio.transcriptions.create.call_args
        assert call_args[1]["prompt"] == prompt
    
    @patch('services.speech_to_text.OpenAI')
    def test_transcribe_api_error(self, mock_openai):
        """测试API调用错误"""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client
        
        service = SpeechToTextService(api_key="test_key")
        
        with pytest.raises(SpeechToTextError, match="转录失败"):
            service.transcribe(self.mock_audio_path)
    
    @patch('services.speech_to_text.OpenAI')
    def test_transcribe_with_timestamps(self, mock_openai):
        """测试带时间戳的转录"""
        # 模拟响应数据
        mock_segment1 = MagicMock()
        mock_segment1.start = 0.0
        mock_segment1.end = 2.5
        mock_segment1.text = " Hello"
        mock_segment1.avg_logprob = -0.2
        
        mock_segment2 = MagicMock()
        mock_segment2.start = 2.5
        mock_segment2.end = 5.0
        mock_segment2.text = " world"
        mock_segment2.avg_logprob = -0.1
        
        mock_response = MagicMock()
        mock_response.text = "Hello world"
        mock_response.language = "en"
        mock_response.duration = 5.0
        mock_response.segments = [mock_segment1, mock_segment2]
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        service = SpeechToTextService(api_key="test_key")
        result = service.transcribe_with_timestamps(self.mock_audio_path)
        
        assert result.text == "Hello world"
        assert result.language == "en"
        assert result.duration == 5.0
        assert len(result.segments) == 2
        
        # 检查第一个片段
        segment1 = result.segments[0]
        assert segment1.start_time == 0.0
        assert segment1.end_time == 2.5
        assert segment1.original_text == "Hello"
        assert segment1.confidence == -0.2
        assert segment1.speaker_id == "speaker_0"
        
        # 检查API调用参数
        call_args = mock_client.audio.transcriptions.create.call_args
        assert call_args[1]["response_format"] == "verbose_json"
        assert call_args[1]["timestamp_granularities"] == ["segment"]
    
    @patch('services.speech_to_text.OpenAI')
    def test_get_timing_data(self, mock_openai):
        """测试获取时序数据"""
        mock_segment = MagicMock()
        mock_segment.start = 0.0
        mock_segment.end = 3.0
        mock_segment.text = " Test segment"
        mock_segment.avg_logprob = -0.15
        
        mock_response = MagicMock()
        mock_response.text = "Test segment"
        mock_response.segments = [mock_segment]
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        service = SpeechToTextService(api_key="test_key")
        segments = service.get_timing_data(self.mock_audio_path)
        
        assert len(segments) == 1
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 3.0
        assert segments[0].original_text == "Test segment"
    
    @patch('services.speech_to_text.OpenAI')
    def test_detect_language(self, mock_openai):
        """测试语言检测"""
        mock_response = MagicMock()
        mock_response.language = "fr"
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        service = SpeechToTextService(api_key="test_key")
        language = service.detect_language(self.mock_audio_path)
        
        assert language == "fr"
    
    def test_detect_language_file_not_exists(self):
        """测试语言检测时文件不存在"""
        with pytest.raises(SpeechToTextError, match="音频文件不存在"):
            self.service.detect_language("/nonexistent/file.wav")
    
    def test_validate_api_key(self):
        """测试API密钥验证"""
        # 这里只是测试方法存在，实际验证需要真实的API密钥
        is_valid = self.service.validate_api_key()
        assert isinstance(is_valid, bool)
    
    def test_get_supported_languages(self):
        """测试获取支持的语言列表"""
        languages = self.service.get_supported_languages()
        
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert 'en' in languages
        assert 'zh' in languages
        assert 'es' in languages
    
    def test_split_long_audio_small_file(self):
        """测试分割小文件"""
        # 小文件应该直接返回
        chunks = self.service.split_long_audio(self.mock_audio_path)
        assert chunks == [self.mock_audio_path]
    
    def test_split_long_audio_large_file(self):
        """测试分割大文件"""
        large_file = os.path.join(self.temp_dir, "large.wav")
        
        with patch('os.path.getsize', return_value=30 * 1024 * 1024):  # 30MB
            with open(large_file, 'w') as f:
                f.write("content")
            
            with pytest.raises(SpeechToTextError, match="音频文件太大"):
                self.service.split_long_audio(large_file)
    
    def test_split_long_audio_file_not_exists(self):
        """测试分割不存在的文件"""
        with pytest.raises(SpeechToTextError, match="音频文件不存在"):
            self.service.split_long_audio("/nonexistent/file.wav")
    
    @patch('services.speech_to_text.OpenAI')
    def test_transcribe_large_file(self, mock_openai):
        """测试转录大文件"""
        # 模拟分割后的文件
        with patch.object(self.service, 'split_long_audio', return_value=[self.mock_audio_path]):
            mock_response = MagicMock()
            mock_response.text = "Large file transcription"
            mock_response.language = "en"
            mock_response.duration = 120.0
            mock_response.segments = []
            
            mock_client = MagicMock()
            mock_client.audio.transcriptions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            service = SpeechToTextService(api_key="test_key")
            result = service.transcribe_large_file(self.mock_audio_path)
            
            assert result.text == "Large file transcription"
            assert result.duration == 120.0
    
    @patch('services.speech_to_text.OpenAI')
    def test_enhance_transcription_quality(self, mock_openai):
        """测试增强转录质量"""
        mock_response = MagicMock()
        mock_response.text = "Enhanced transcription"
        mock_response.segments = []
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        service = SpeechToTextService(api_key="test_key")
        result = service.enhance_transcription_quality(
            self.mock_audio_path, 
            context="Technical meeting about AI"
        )
        
        assert result.text == "Enhanced transcription"
        
        # 验证API调用包含了上下文提示
        call_args = mock_client.audio.transcriptions.create.call_args
        prompt = call_args[1]["prompt"]
        assert "Context: Technical meeting about AI" in prompt
        assert "Please transcribe accurately" in prompt