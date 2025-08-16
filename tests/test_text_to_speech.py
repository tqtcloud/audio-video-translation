import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pydub import AudioSegment
from services.text_to_speech import TextToSpeechService, TextToSpeechServiceError, VoiceConfig
from services.providers import SpeechSynthesisResult
from models.core import TimedSegment


class TestTextToSpeechService:
    
    def setup_method(self):
        # 模拟提供者
        with patch('services.text_to_speech.provider_manager') as mock_manager:
            mock_provider = MagicMock()
            mock_manager.get_tts_provider.return_value = mock_provider
            self.service = TextToSpeechService()
            self.mock_provider = mock_provider
        
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
        self.test_audio = AudioSegment.silent(duration=2000)  # 2秒静音
    
    def test_initialization_with_provider_type(self):
        """测试使用指定提供者类型初始化"""
        with patch('services.text_to_speech.provider_manager') as mock_manager:
            service = TextToSpeechService(api_key="test_key")
            assert service.api_key == "test_key"
            assert 'en' in service.voice_mapping
            assert 'zh' in service.voice_mapping
    
    def test_initialization_without_api_key(self):
        """测试没有API密钥时的初始化"""
        with patch('services.text_to_speech.Config.OPENAI_API_KEY', ''):
            with patch('services.text_to_speech.which', return_value='/usr/bin/ffmpeg'):
                with pytest.raises(TextToSpeechServiceError, match="未提供 OpenAI API 密钥"):
                    TextToSpeechService()
    
    def test_initialization_without_ffmpeg(self):
        """测试没有FFmpeg时的初始化"""
        with patch('services.text_to_speech.which', return_value=None):
            with pytest.raises(TextToSpeechServiceError, match="未找到 FFmpeg"):
                TextToSpeechService(api_key="test_key")
    
    def test_get_supported_voices_valid_language(self):
        """测试获取支持的语音列表"""
        voices = self.service.get_supported_voices('en')
        
        assert isinstance(voices, dict)
        assert 'male' in voices
        assert 'female' in voices
        assert 'default' in voices
        assert voices['default'] == 'alloy'
    
    def test_get_supported_voices_invalid_language(self):
        """测试不支持的语言"""
        voices = self.service.get_supported_voices('unsupported')
        assert voices == {}
    
    def test_synthesize_text_empty_input(self):
        """测试空文本合成"""
        with pytest.raises(TextToSpeechServiceError, match="输入文本为空"):
            self.service.synthesize_text("", 'zh')
        
        with pytest.raises(TextToSpeechServiceError, match="输入文本为空"):
            self.service.synthesize_text("   ", 'zh')
    
    def test_synthesize_text_unsupported_language(self):
        """测试不支持的语言合成"""
        with pytest.raises(TextToSpeechServiceError, match="不支持的语言"):
            self.service.synthesize_text("Hello", 'unsupported')
    
    @patch('services.text_to_speech.openai.audio.speech.create')
    def test_synthesize_text_success(self, mock_openai):
        """测试成功的文本合成"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.content = b"fake_audio_data"
        mock_openai.return_value = mock_response
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result_path = self.service.synthesize_text("你好世界", 'zh')
            
            assert os.path.exists(result_path)
            assert result_path.endswith('.mp3')
            
            # 清理临时文件
            os.unlink(result_path)
    
    def test_synthesize_speech_empty_input(self):
        """测试空片段列表合成"""
        with pytest.raises(TextToSpeechServiceError, match="输入片段列表为空"):
            self.service.synthesize_speech([], 'zh')
    
    def test_synthesize_speech_unsupported_language(self):
        """测试不支持的语言合成"""
        with pytest.raises(TextToSpeechServiceError, match="不支持的语言"):
            self.service.synthesize_speech(self.test_segments, 'unsupported')
    
    @patch('services.text_to_speech.openai.audio.speech.create')
    @patch('services.text_to_speech.tempfile.NamedTemporaryFile')
    def test_synthesize_speech_success(self, mock_tempfile, mock_openai):
        """测试成功的语音合成"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.content = b"fake_audio_data"
        mock_openai.return_value = mock_response
        
        # 模拟临时文件
        mock_temp = Mock()
        mock_temp.name = "/tmp/test_audio.mp3"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        mock_tempfile.return_value.__exit__.return_value = None
        
        # 模拟文件操作
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.write = Mock()
            
            # 模拟 AudioSegment.from_file
            with patch('services.text_to_speech.AudioSegment.from_file') as mock_from_file:
                mock_from_file.return_value = self.test_audio
                
                # 模拟 AudioSegment.export
                with patch.object(self.test_audio, 'export') as mock_export:
                    mock_export.return_value = None
                    
                    result = self.service.synthesize_speech(self.test_segments, 'zh')
        
        assert isinstance(result, SpeechSynthesisResult)
        assert result.segments_count == 3
        assert result.quality_score >= 0.0
        assert result.processing_time > 0.0
    
    def test_voice_config_creation(self):
        """测试语音配置创建"""
        config = VoiceConfig(
            voice_id="nova",
            language="en",
            speed=1.2,
            pitch=0.1,
            emotion="happy"
        )
        
        assert config.voice_id == "nova"
        assert config.language == "en"
        assert config.speed == 1.2
        assert config.pitch == 0.1
        assert config.emotion == "happy"
    
    def test_voice_config_defaults(self):
        """测试语音配置默认值"""
        config = VoiceConfig(voice_id="alloy", language="zh")
        
        assert config.speed == 1.0
        assert config.pitch == 0.0
        assert config.emotion == "neutral"
    
    @patch('services.text_to_speech.AudioSegment.from_file')
    def test_adjust_speech_timing_success(self, mock_from_file):
        """测试成功的语音时序调整"""
        # 模拟音频文件
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=2000)  # 2秒
        mock_from_file.return_value = mock_audio
        
        # 模拟速度调整
        with patch.object(self.service, '_adjust_audio_speed', return_value=mock_audio) as mock_adjust:
            with patch.object(mock_audio, 'export') as mock_export:
                result_path = self.service.adjust_speech_timing("/fake/path.mp3", 3.0)
                
                assert result_path.endswith('.mp3')
                mock_adjust.assert_called_once()
                mock_export.assert_called_once()
    
    def test_split_text_into_chunks_short_text(self):
        """测试短文本分块"""
        short_text = "这是一个短文本。"
        chunks = self.service._split_text_into_chunks(short_text)
        
        assert len(chunks) == 1
        assert chunks[0] == short_text
    
    def test_split_text_into_chunks_long_text(self):
        """测试长文本分块"""
        # 创建带有正确句号分隔的长文本
        long_text = "这是第一句。这是第二句。这是第三句。这是第四句。这是第五句。"
        
        # 确保文本长度超过限制
        actual_length = len(long_text)
        self.service.max_text_length = 20  # 设置更小的限制，确保需要分块
        
        chunks = self.service._split_text_into_chunks(long_text)
        
        # 由于文本总长度 > 20，应该分成多块
        assert len(chunks) > 1
        # 验证所有块的长度都合理
        total_chars = sum(len(chunk) for chunk in chunks)
        assert total_chars <= actual_length + 10  # 允许一定的格式化开销
    
    def test_analyze_audio_quality_good_audio(self):
        """测试良好音频的质量分析"""
        # 创建模拟音频
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=2000)  # 2秒
        mock_audio.dBFS = -20  # 合适的音量
        mock_audio.frame_rate = 44100  # 高采样率
        
        quality = self.service._analyze_audio_quality(mock_audio)
        assert quality >= 0.8
    
    def test_analyze_audio_quality_poor_audio(self):
        """测试低质量音频的分析"""
        # 创建模拟音频
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=50)  # 太短
        mock_audio.dBFS = -50  # 太安静
        mock_audio.frame_rate = 8000  # 低采样率
        
        quality = self.service._analyze_audio_quality(mock_audio)
        assert quality < 0.8
    
    def test_analyze_audio_quality_exception(self):
        """测试音频分析异常处理"""
        # 创建会抛出异常的模拟音频
        mock_audio = Mock()
        # 直接设置属性访问异常
        type(mock_audio).__len__ = Mock(side_effect=Exception("测试异常"))
        
        quality = self.service._analyze_audio_quality(mock_audio)
        assert quality == 0.5
    
    def test_check_segment_completeness_normal(self):
        """测试正常片段完整性检查"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)  # 6秒
        
        completeness = self.service._check_segment_completeness(self.test_segments, mock_audio)
        assert completeness > 0.0
    
    def test_check_segment_completeness_empty_segments(self):
        """测试空片段的完整性检查"""
        mock_audio = Mock()
        completeness = self.service._check_segment_completeness([], mock_audio)
        assert completeness == 0.0
    
    def test_calculate_synthesis_quality_good(self):
        """测试良好合成质量计算"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)  # 6秒，匹配测试片段总时长
        
        with patch.object(self.service, '_analyze_audio_quality', return_value=0.9):
            quality = self.service._calculate_synthesis_quality(
                self.test_segments, mock_audio, []
            )
            assert quality > 0.7
    
    def test_calculate_synthesis_quality_with_adjustments(self):
        """测试有时序调整的合成质量计算"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)
        timing_adjustments = [(0, 1.2), (1, 0.8)]  # 2个调整
        
        with patch.object(self.service, '_analyze_audio_quality', return_value=0.8):
            quality = self.service._calculate_synthesis_quality(
                self.test_segments, mock_audio, timing_adjustments
            )
            # 有调整会降低质量分数
            assert quality < 0.9
    
    @patch('services.text_to_speech.AudioSegment.from_file')
    def test_validate_synthesis_quality_success(self, mock_from_file):
        """测试语音合成质量验证"""
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=6000)  # 6秒
        mock_from_file.return_value = mock_audio
        
        with patch.object(self.service, '_analyze_audio_quality', return_value=0.8):
            with patch.object(self.service, '_check_segment_completeness', return_value=0.9):
                result = self.service.validate_synthesis_quality(
                    self.test_segments, "/fake/path.mp3"
                )
                
                assert 'timing_accuracy' in result
                assert 'audio_quality' in result
                assert 'completeness' in result
                assert 'overall_score' in result
                assert all(0.0 <= v <= 1.0 for v in result.values())
    
    def test_validate_synthesis_quality_exception(self):
        """测试质量验证异常处理"""
        with patch('services.text_to_speech.AudioSegment.from_file', side_effect=Exception("文件错误")):
            result = self.service.validate_synthesis_quality(
                self.test_segments, "/fake/path.mp3"
            )
            
            # 异常时应返回零分
            assert all(v == 0.0 for v in result.values())
    
    def test_combine_audio_segments_empty(self):
        """测试空音频片段合并"""
        result = self.service._combine_audio_segments([], [])
        assert len(result) == 1000  # 1秒静音
    
    def test_combine_audio_segments_with_gaps(self):
        """测试带间隙的音频片段合并"""
        # 创建有时间间隙的片段
        gapped_segments = [
            TimedSegment(start_time=0.0, end_time=1.0, original_text="", translated_text="Hello"),
            TimedSegment(start_time=2.0, end_time=3.0, original_text="", translated_text="World")  # 1秒间隙
        ]
        
        audio_segments = [self.test_audio, self.test_audio]
        
        with patch('services.text_to_speech.AudioSegment.silent') as mock_silent:
            mock_silent.return_value = AudioSegment.silent(duration=500)
            
            result = self.service._combine_audio_segments(audio_segments, gapped_segments)
            
            # 应该调用静音生成
            mock_silent.assert_called()
    
    @patch('services.text_to_speech.os.system')
    def test_adjust_audio_speed_success(self, mock_system):
        """测试音频速度调整"""
        # 模拟FFmpeg成功执行
        mock_system.return_value = 0
        
        with patch('services.text_to_speech.AudioSegment.from_wav', return_value=self.test_audio):
            result = self.service._adjust_audio_speed(self.test_audio, 1.2)
            assert result is not None
            mock_system.assert_called_once()
    
    @patch('services.text_to_speech.os.system')
    def test_adjust_audio_speed_failure(self, mock_system):
        """测试音频速度调整失败"""
        # 模拟FFmpeg失败
        mock_system.return_value = 1
        
        with patch('services.text_to_speech.AudioSegment.from_wav', side_effect=Exception("加载失败")):
            result = self.service._adjust_audio_speed(self.test_audio, 1.2)
            # 失败时应返回原音频
            assert result == self.test_audio
    
    def test_merge_audio_chunks(self):
        """测试音频块合并"""
        audio_chunks = [b"chunk1", b"chunk2", b"chunk3"]
        
        # 使用实际的AudioSegment进行测试
        with patch('services.text_to_speech.AudioSegment.from_file', return_value=self.test_audio):
            # Mock the final export and read operations
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = b"merged_audio"
                
                # Mock the export method on AudioSegment
                with patch.object(AudioSegment, 'export') as mock_export:
                    result = self.service._merge_audio_chunks(audio_chunks)
                    
                    assert result == b"merged_audio"
                    # 合并后的音频应该被导出
                    assert mock_export.called