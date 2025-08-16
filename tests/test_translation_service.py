import pytest
from unittest.mock import Mock, patch, MagicMock
from services.translation_service import TranslationService, TranslationServiceError, TranslationResult
from models.core import TimedSegment


class TestTranslationService:
    
    def setup_method(self):
        # 使用模拟的API密钥初始化服务
        with patch.object(TranslationService, '_call_translation_api_with_retry'):
            self.service = TranslationService(api_key="test_api_key")
        
        # 创建测试数据
        self.test_segments = [
            TimedSegment(
                start_time=0.0,
                end_time=2.5,
                original_text="Hello world",
                confidence=-0.1,
                speaker_id="speaker_1"
            ),
            TimedSegment(
                start_time=2.5,
                end_time=5.0,
                original_text="How are you today",
                confidence=-0.3,
                speaker_id="speaker_1"
            ),
            TimedSegment(
                start_time=5.0,
                end_time=7.5,
                original_text="I am fine thank you",
                confidence=-0.15,
                speaker_id="speaker_2"
            )
        ]
    
    def test_initialization_with_api_key(self):
        """测试使用API密钥初始化"""
        service = TranslationService(api_key="test_key")
        assert service.api_key == "test_key"
        assert service.language_map['en'] == 'English'
        assert service.language_map['zh'] == 'Chinese'
    
    def test_initialization_without_api_key(self):
        """测试没有API密钥时的初始化"""
        with patch('services.translation_service.Config.OPENAI_API_KEY', ''):
            with pytest.raises(TranslationServiceError, match="未提供 OpenAI API 密钥"):
                TranslationService()
    
    def test_get_supported_languages(self):
        """测试获取支持的语言列表"""
        languages = self.service.get_supported_languages()
        
        assert isinstance(languages, dict)
        assert 'en' in languages
        assert 'zh' in languages
        assert 'es' in languages
        assert 'fr' in languages
        assert 'de' in languages
        assert languages['en'] == 'English'
        assert languages['zh'] == 'Chinese'
    
    def test_detect_text_language_chinese(self):
        """测试中文语言检测"""
        chinese_text = "你好世界，今天天气怎么样？"
        result = self.service._detect_text_language(chinese_text)
        assert result == 'zh'
    
    def test_detect_text_language_english(self):
        """测试英文语言检测"""
        english_text = "Hello world, how are you today?"
        result = self.service._detect_text_language(english_text)
        assert result == 'en'
    
    def test_detect_text_language_german(self):
        """测试德语语言检测"""
        german_text = "Hallo, wie geht es dir heute? Das ist schön."
        result = self.service._detect_text_language(german_text)
        assert result == 'de'
    
    def test_detect_text_language_french(self):
        """测试法语语言检测"""
        french_text = "Bonjour, comment allez-vous? C'est très bien."
        result = self.service._detect_text_language(french_text)
        assert result == 'fr'
    
    def test_detect_text_language_spanish(self):
        """测试西班牙语语言检测"""
        spanish_text = "Hola, ¿cómo estás hoy? Muy bien, gracias."
        result = self.service._detect_text_language(spanish_text)
        assert result == 'es'
    
    def test_batch_segments_single_batch(self):
        """测试单批次分割"""
        # 设置较大的限制，所有片段都应该在一个批次中
        self.service.max_tokens_per_request = 1000
        
        batches = self.service._batch_segments(self.test_segments)
        
        assert len(batches) == 1
        assert len(batches[0]) == 3
        assert batches[0] == self.test_segments
    
    def test_batch_segments_multiple_batches(self):
        """测试多批次分割"""
        # 设置较小的限制，强制分割
        self.service.max_tokens_per_request = 20
        
        batches = self.service._batch_segments(self.test_segments)
        
        assert len(batches) > 1
        # 验证所有片段都被包含
        all_segments = []
        for batch in batches:
            all_segments.extend(batch)
        assert len(all_segments) == len(self.test_segments)
    
    def test_batch_segments_empty_input(self):
        """测试空输入的批次分割"""
        batches = self.service._batch_segments([])
        assert batches == []
    
    @patch('services.translation_service.openai.ChatCompletion.create')
    def test_call_translation_api_with_retry_success(self, mock_openai):
        """测试成功的API调用"""
        # 模拟成功的API响应
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "翻译结果"
        mock_openai.return_value = mock_response
        
        result = self.service._call_translation_api_with_retry("测试提示")
        
        assert result == "翻译结果"
        assert mock_openai.call_count == 1
    
    @patch('services.translation_service.openai.ChatCompletion.create')
    def test_call_translation_api_with_retry_failure(self, mock_openai):
        """测试API调用失败后重试"""
        # 模拟API调用失败
        mock_openai.side_effect = Exception("API错误")
        
        with pytest.raises(TranslationServiceError, match="API调用失败"):
            self.service._call_translation_api_with_retry("测试提示")
        
        assert mock_openai.call_count == self.service.max_retries
    
    @patch('services.translation_service.openai.ChatCompletion.create')
    def test_call_translation_api_with_retry_eventual_success(self, mock_openai):
        """测试重试后成功的API调用"""
        # 前两次失败，第三次成功
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "成功翻译"
        
        mock_openai.side_effect = [
            Exception("第一次失败"),
            Exception("第二次失败"),
            mock_response
        ]
        
        result = self.service._call_translation_api_with_retry("测试提示")
        
        assert result == "成功翻译"
        assert mock_openai.call_count == 3
    
    def test_translate_text_same_language(self):
        """测试相同语言的翻译"""
        text = "Hello world"
        
        with patch.object(self.service, '_detect_text_language', return_value='en'):
            result = self.service.translate_text(text, 'en')
        
        assert result == text
    
    def test_translate_text_empty_input(self):
        """测试空文本翻译"""
        result = self.service.translate_text("", 'zh')
        assert result == ""
        
        result = self.service.translate_text("   ", 'zh')
        assert result == ""
    
    def test_translate_text_unsupported_language(self):
        """测试不支持的语言"""
        with pytest.raises(TranslationServiceError, match="不支持的目标语言"):
            self.service.translate_text("Hello", 'unsupported')
    
    @patch('services.translation_service.openai.ChatCompletion.create')
    def test_translate_text_success(self, mock_openai):
        """测试成功的文本翻译"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "你好世界"
        mock_openai.return_value = mock_response
        
        with patch.object(self.service, '_detect_text_language', return_value='en'):
            result = self.service.translate_text("Hello world", 'zh')
        
        assert result == "你好世界"
    
    def test_translate_segments_empty_input(self):
        """测试空片段列表翻译"""
        with pytest.raises(TranslationServiceError, match="输入片段列表为空"):
            self.service.translate_segments([], 'zh')
    
    def test_translate_segments_unsupported_target_language(self):
        """测试不支持的目标语言"""
        with pytest.raises(TranslationServiceError, match="不支持的目标语言"):
            self.service.translate_segments(self.test_segments, 'unsupported')
    
    def test_translate_segments_same_language(self):
        """测试相同语言的片段翻译"""
        with patch.object(self.service, '_detect_language', return_value='en'):
            result = self.service.translate_segments(self.test_segments, 'en')
        
        assert isinstance(result, TranslationResult)
        assert len(result.translated_segments) == len(self.test_segments)
        assert result.language_detected == 'en'
        assert result.quality_score == 1.0
        
        # 验证翻译文本与原文相同
        for orig, trans in zip(self.test_segments, result.translated_segments):
            assert trans.translated_text == orig.original_text
            assert trans.start_time == orig.start_time
            assert trans.end_time == orig.end_time
    
    @patch('services.translation_service.openai.ChatCompletion.create')
    def test_translate_segments_success(self, mock_openai):
        """测试成功的片段翻译"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """1. 你好世界
2. 你今天怎么样
3. 我很好谢谢你"""
        mock_openai.return_value = mock_response
        
        with patch.object(self.service, '_detect_language', return_value='en'):
            result = self.service.translate_segments(self.test_segments, 'zh')
        
        assert isinstance(result, TranslationResult)
        assert len(result.translated_segments) == 3
        assert result.language_detected == 'en'
        assert result.quality_score > 0
        
        # 验证翻译结果
        assert result.translated_segments[0].translated_text == "你好世界"
        assert result.translated_segments[1].translated_text == "你今天怎么样"
        assert result.translated_segments[2].translated_text == "我很好谢谢你"
        
        # 验证时序信息保持不变
        for orig, trans in zip(self.test_segments, result.translated_segments):
            assert trans.start_time == orig.start_time
            assert trans.end_time == orig.end_time
            assert trans.confidence == orig.confidence
            assert trans.speaker_id == orig.speaker_id
    
    def test_calculate_quality_score_empty_input(self):
        """测试空输入的质量评分"""
        score = self.service._calculate_quality_score([], [])
        assert score == 0.0
    
    def test_calculate_quality_score_length_mismatch(self):
        """测试长度不匹配的质量评分"""
        translated = self.test_segments[:2]  # 少一个片段
        score = self.service._calculate_quality_score(self.test_segments, translated)
        assert score == 0.5
    
    def test_calculate_quality_score_good_translation(self):
        """测试质量良好的翻译评分"""
        # 创建合理长度的翻译片段
        translated_segments = []
        for seg in self.test_segments:
            translated_seg = TimedSegment(
                start_time=seg.start_time,
                end_time=seg.end_time,
                original_text=seg.original_text,
                translated_text="翻译文本" * max(1, len(seg.original_text) // 4),  # 更合理的长度比例
                confidence=seg.confidence,
                speaker_id=seg.speaker_id
            )
            translated_segments.append(translated_seg)
        
        score = self.service._calculate_quality_score(self.test_segments, translated_segments)
        assert score > 0.3
    
    def test_calculate_quality_score_empty_translations(self):
        """测试空翻译的质量评分"""
        # 创建空翻译片段
        translated_segments = []
        for seg in self.test_segments:
            translated_seg = TimedSegment(
                start_time=seg.start_time,
                end_time=seg.end_time,
                original_text=seg.original_text,
                translated_text="",  # 空翻译
                confidence=seg.confidence,
                speaker_id=seg.speaker_id
            )
            translated_segments.append(translated_seg)
        
        score = self.service._calculate_quality_score(self.test_segments, translated_segments)
        assert score < 0.5  # 空翻译应该得到较低分数
    
    def test_validate_translation_quality_length_mismatch(self):
        """测试长度不匹配的翻译质量验证"""
        translated = self.test_segments[:2]
        result = self.service.validate_translation_quality(self.test_segments, translated)
        
        assert result['timing_accuracy'] == 0.0
        assert result['length_consistency'] == 0.0
        assert result['overall_score'] == 0.0
    
    def test_validate_translation_quality_perfect_match(self):
        """测试完美匹配的翻译质量验证"""
        # 创建完全匹配的翻译片段
        translated_segments = []
        for seg in self.test_segments:
            translated_seg = TimedSegment(
                start_time=seg.start_time,
                end_time=seg.end_time,
                original_text=seg.original_text,
                translated_text=seg.original_text,  # 相同长度
                confidence=seg.confidence,
                speaker_id=seg.speaker_id
            )
            translated_segments.append(translated_seg)
        
        result = self.service.validate_translation_quality(self.test_segments, translated_segments)
        
        assert result['timing_accuracy'] == 1.0
        assert result['length_consistency'] == 1.0
        assert result['overall_score'] == 1.0
    
    def test_calculate_timing_accuracy_perfect(self):
        """测试完美时序准确性"""
        # 使用相同的时序信息
        accuracy = self.service._calculate_timing_accuracy(self.test_segments, self.test_segments)
        assert accuracy == 1.0
    
    def test_calculate_timing_accuracy_mismatch(self):
        """测试时序不匹配的准确性"""
        # 创建时序偏移的片段
        offset_segments = []
        for seg in self.test_segments:
            offset_seg = TimedSegment(
                start_time=seg.start_time + 1.0,  # 偏移1秒
                end_time=seg.end_time + 1.0,
                original_text=seg.original_text,
                confidence=seg.confidence,
                speaker_id=seg.speaker_id
            )
            offset_segments.append(offset_seg)
        
        accuracy = self.service._calculate_timing_accuracy(self.test_segments, offset_segments)
        assert accuracy == 0.0
    
    def test_calculate_length_consistency_perfect(self):
        """测试完美长度一致性"""
        # 创建具有相同长度的翻译片段
        same_length_segments = []
        for seg in self.test_segments:
            same_seg = TimedSegment(
                start_time=seg.start_time,
                end_time=seg.end_time,
                original_text=seg.original_text,
                translated_text=seg.original_text,  # 相同的文本
                confidence=seg.confidence,
                speaker_id=seg.speaker_id
            )
            same_length_segments.append(same_seg)
        
        consistency = self.service._calculate_length_consistency(self.test_segments, same_length_segments)
        assert consistency == 1.0
    
    def test_calculate_length_consistency_poor(self):
        """测试较差的长度一致性"""
        # 创建长度差异很大的翻译
        poor_segments = []
        for seg in self.test_segments:
            poor_seg = TimedSegment(
                start_time=seg.start_time,
                end_time=seg.end_time,
                original_text=seg.original_text,
                translated_text="short",  # 很短的翻译
                confidence=seg.confidence,
                speaker_id=seg.speaker_id
            )
            poor_segments.append(poor_seg)
        
        consistency = self.service._calculate_length_consistency(self.test_segments, poor_segments)
        assert consistency < 1.0