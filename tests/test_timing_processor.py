import pytest
from services.timing_processor import TimingProcessor, TimingProcessorError, SpeakerStats, TimingQualityMetrics
from models.core import TimedSegment


class TestTimingProcessor:
    
    def setup_method(self):
        self.processor = TimingProcessor()
        
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
                start_time=7.0,
                end_time=9.5,
                original_text="I am fine thank you",
                confidence=-0.15,
                speaker_id="speaker_2"
            )
        ]
    
    def test_confidence_thresholds(self):
        """测试置信度阈值设置"""
        expected_thresholds = {
            'high': -0.2,
            'medium': -0.5,
            'low': -1.0
        }
        assert self.processor.confidence_thresholds == expected_thresholds
    
    def test_extract_word_level_timing_empty_input(self):
        """测试空输入的词级时序提取"""
        result = self.processor.extract_word_level_timing([])
        assert result == []
    
    def test_extract_word_level_timing_success(self):
        """测试成功的词级时序提取"""
        segments = [
            TimedSegment(
                start_time=0.0,
                end_time=4.0,
                original_text="Hello world test",
                confidence=-0.2,
                speaker_id="speaker_1"
            )
        ]
        
        result = self.processor.extract_word_level_timing(segments)
        
        assert len(result) == 3  # "Hello", "world", "test"
        
        # 检查第一个单词
        assert result[0].start_time == 0.0
        assert abs(result[0].end_time - 4.0/3) < 0.01
        assert result[0].original_text == "Hello"
        assert result[0].confidence == -0.2
        assert result[0].speaker_id == "speaker_1"
        
        # 检查最后一个单词的结束时间
        assert result[-1].end_time == 4.0
    
    def test_extract_word_level_timing_empty_text(self):
        """测试空文本的处理"""
        segments = [
            TimedSegment(
                start_time=0.0,
                end_time=2.0,
                original_text="",
                confidence=-0.2,
                speaker_id="speaker_1"
            )
        ]
        
        result = self.processor.extract_word_level_timing(segments)
        assert result == []
    
    def test_identify_speakers_empty_input(self):
        """测试空输入的说话人识别"""
        result = self.processor.identify_speakers([])
        assert result == []
    
    def test_identify_speakers_single_segment(self):
        """测试单个片段的说话人识别"""
        segments = [self.test_segments[0]]
        
        result = self.processor.identify_speakers(segments)
        
        assert len(result) == 1
        assert result[0].speaker_id == "speaker_1"
    
    def test_identify_speakers_with_silence_detection(self):
        """测试基于静音的说话人识别"""
        segments = [
            TimedSegment(start_time=0.0, end_time=2.0, original_text="Hello", confidence=-0.1),
            TimedSegment(start_time=5.0, end_time=7.0, original_text="World", confidence=-0.2)  # 3秒间隙
        ]
        
        result = self.processor.identify_speakers(segments, use_silence_detection=True)
        
        assert len(result) == 2
        assert result[0].speaker_id == "speaker_1"
        assert result[1].speaker_id == "speaker_2"  # 应该识别为不同说话人
    
    def test_identify_speakers_no_silence_detection(self):
        """测试不使用静音检测的说话人识别"""
        segments = [
            TimedSegment(start_time=0.0, end_time=2.0, original_text="Hello", confidence=-0.1),
            TimedSegment(start_time=5.0, end_time=7.0, original_text="World", confidence=-0.2)
        ]
        
        result = self.processor.identify_speakers(segments, use_silence_detection=False)
        
        assert len(result) == 2
        # 不使用静音检测时，两个片段可能被识别为同一说话人
    
    def test_calculate_confidence_scores_empty_input(self):
        """测试空输入的置信度计算"""
        result = self.processor.calculate_confidence_scores([])
        
        expected = {
            'average_confidence': 0.0,
            'high_confidence_ratio': 0.0,
            'medium_confidence_ratio': 0.0,
            'low_confidence_ratio': 0.0,
            'total_segments': 0
        }
        assert result == expected
    
    def test_calculate_confidence_scores_success(self):
        """测试成功的置信度计算"""
        segments = [
            TimedSegment(start_time=0.0, end_time=1.0, original_text="high", confidence=-0.1),    # high
            TimedSegment(start_time=1.0, end_time=2.0, original_text="medium", confidence=-0.3),  # medium
            TimedSegment(start_time=2.0, end_time=3.0, original_text="low", confidence=-0.7)      # low
        ]
        
        result = self.processor.calculate_confidence_scores(segments)
        
        assert result['total_segments'] == 3
        assert abs(result['average_confidence'] - (-0.1 - 0.3 - 0.7) / 3) < 0.01
        assert result['high_confidence_ratio'] == 1/3
        assert result['medium_confidence_ratio'] == 1/3
        assert result['low_confidence_ratio'] == 1/3
    
    def test_calculate_confidence_scores_no_confidence(self):
        """测试没有置信度的片段"""
        segments = [
            TimedSegment(start_time=0.0, end_time=1.0, original_text="test", confidence=None)
        ]
        
        result = self.processor.calculate_confidence_scores(segments)
        
        assert result['total_segments'] == 1
        assert result['average_confidence'] == 0.0
        assert result['high_confidence_ratio'] == 0.0
    
    def test_analyze_timing_quality_empty_input(self):
        """测试空输入的时序质量分析"""
        result = self.processor.analyze_timing_quality([])
        
        assert result.total_segments == 0
        assert result.average_segment_duration == 0.0
        assert result.confidence_distribution == {'high': 0, 'medium': 0, 'low': 0}
    
    def test_analyze_timing_quality_success(self):
        """测试成功的时序质量分析"""
        result = self.processor.analyze_timing_quality(self.test_segments)
        
        assert result.total_segments == 3
        assert result.average_segment_duration > 0
        assert 'speaker_1' in result.speaker_distribution
        assert 'speaker_2' in result.speaker_distribution
        assert result.speaker_distribution['speaker_1'] == 2
        assert result.speaker_distribution['speaker_2'] == 1
        
        # 检查间隙计算（第二和第三个片段之间有间隙）
        assert result.gaps_count == 1
        assert result.total_silence_time > 0
    
    def test_get_speaker_statistics_empty_input(self):
        """测试空输入的说话人统计"""
        result = self.processor.get_speaker_statistics([])
        assert result == []
    
    def test_get_speaker_statistics_success(self):
        """测试成功的说话人统计"""
        result = self.processor.get_speaker_statistics(self.test_segments)
        
        assert len(result) == 2
        
        # 按发言时长排序，speaker_1应该排在前面
        speaker1_stats = next(s for s in result if s.speaker_id == "speaker_1")
        speaker2_stats = next(s for s in result if s.speaker_id == "speaker_2")
        
        assert speaker1_stats.segment_count == 2
        assert speaker2_stats.segment_count == 1
        assert speaker1_stats.total_duration == 5.0  # 2.5 + 2.5
        assert speaker2_stats.total_duration == 2.5
        assert speaker1_stats.word_count > 0
    
    def test_merge_adjacent_segments_empty_input(self):
        """测试空输入的片段合并"""
        result = self.processor.merge_adjacent_segments([])
        assert result == []
    
    def test_merge_adjacent_segments_success(self):
        """测试成功的片段合并"""
        segments = [
            TimedSegment(start_time=0.0, end_time=1.0, original_text="Hello", 
                        confidence=-0.1, speaker_id="speaker_1"),
            TimedSegment(start_time=1.1, end_time=2.0, original_text="world", 
                        confidence=-0.2, speaker_id="speaker_1")  # 0.1秒间隙，应该合并
        ]
        
        result = self.processor.merge_adjacent_segments(segments, max_gap=0.2)
        
        assert len(result) == 1
        assert result[0].start_time == 0.0
        assert result[0].end_time == 2.0
        assert "Hello world" in result[0].original_text
        assert result[0].speaker_id == "speaker_1"
    
    def test_merge_adjacent_segments_no_merge(self):
        """测试不合并的情况"""
        segments = [
            TimedSegment(start_time=0.0, end_time=1.0, original_text="Hello", 
                        confidence=-0.1, speaker_id="speaker_1"),
            TimedSegment(start_time=2.0, end_time=3.0, original_text="world", 
                        confidence=-0.2, speaker_id="speaker_2")  # 不同说话人
        ]
        
        result = self.processor.merge_adjacent_segments(segments, max_gap=0.2)
        
        assert len(result) == 2  # 不应该合并
    
    def test_filter_by_confidence(self):
        """测试按置信度过滤"""
        segments = [
            TimedSegment(start_time=0.0, end_time=1.0, original_text="high", confidence=-0.1),
            TimedSegment(start_time=1.0, end_time=2.0, original_text="low", confidence=-0.7),
            TimedSegment(start_time=2.0, end_time=3.0, original_text="none", confidence=None)
        ]
        
        result = self.processor.filter_by_confidence(segments, min_confidence=-0.5)
        
        assert len(result) == 1
        assert result[0].original_text == "high"
    
    def test_split_text_to_words_english(self):
        """测试英文文本分词"""
        text = "Hello, world! How are you?"
        result = self.processor._split_text_to_words(text)
        
        expected = ["Hello", "world!", "How", "are", "you?"]
        assert result == expected
    
    def test_split_text_to_words_chinese(self):
        """测试中文文本分词"""
        text = "你好，世界！你好吗？"
        result = self.processor._split_text_to_words(text)
        
        # 简单的分词，按标点分割
        assert len(result) > 0
        assert "你好" in result[0]
    
    def test_split_text_to_words_empty(self):
        """测试空文本分词"""
        result = self.processor._split_text_to_words("")
        assert result == []
        
        result = self.processor._split_text_to_words("   ")
        assert result == []
    
    def test_detect_speaker_change_by_text_sentence_ending(self):
        """测试基于句子结束的说话人切换检测"""
        prev_seg = TimedSegment(start_time=0.0, end_time=2.0, original_text="Hello world.")
        curr_seg = TimedSegment(start_time=2.0, end_time=4.0, original_text="How are you?")
        
        result = self.processor._detect_speaker_change_by_text(prev_seg, curr_seg)
        assert result is True
    
    def test_detect_speaker_change_by_text_question(self):
        """测试基于问句的说话人切换检测"""
        prev_seg = TimedSegment(start_time=0.0, end_time=2.0, original_text="How are you?")
        curr_seg = TimedSegment(start_time=2.0, end_time=4.0, original_text="I am fine")
        
        result = self.processor._detect_speaker_change_by_text(prev_seg, curr_seg)
        assert result is True
    
    def test_detect_speaker_change_by_text_no_change(self):
        """测试没有说话人切换的情况"""
        prev_seg = TimedSegment(start_time=0.0, end_time=2.0, original_text="Hello there")
        curr_seg = TimedSegment(start_time=2.0, end_time=4.0, original_text="my friend")
        
        result = self.processor._detect_speaker_change_by_text(prev_seg, curr_seg)
        assert result is False
    
    def test_timing_processor_error_handling(self):
        """测试错误处理"""
        # 测试无效输入导致的错误
        with pytest.raises(TimingProcessorError):
            # 创建一个会导致错误的情况（这里模拟一个会抛出异常的场景）
            segments = [None]  # 无效的片段
            self.processor.extract_word_level_timing(segments)