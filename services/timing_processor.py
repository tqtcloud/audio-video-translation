import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from models.core import TimedSegment


class TimingProcessorError(Exception):
    """时序处理器错误"""
    pass


@dataclass
class SpeakerStats:
    """说话人统计信息"""
    speaker_id: str
    total_duration: float
    segment_count: int
    average_confidence: float
    word_count: int


@dataclass
class TimingQualityMetrics:
    """时序质量评估指标"""
    total_segments: int
    average_segment_duration: float
    confidence_distribution: Dict[str, int]  # low, medium, high
    speaker_distribution: Dict[str, int]
    gaps_count: int
    overlaps_count: int
    total_speech_time: float
    total_silence_time: float


class TimingProcessor:
    """
    时序数据处理器
    
    提取词级时序数据，实现说话人识别功能，
    生成置信度分数用于质量评估。
    """
    
    def __init__(self):
        # 置信度阈值
        self.confidence_thresholds = {
            'high': -0.2,
            'medium': -0.5,
            'low': -1.0
        }
        
        # 说话人识别参数
        self.silence_threshold = 0.5  # 静音阈值（秒）
        self.speaker_change_threshold = 2.0  # 说话人切换阈值（秒）
        
        # 文本处理模式
        self.sentence_endings = r'[.!?。！？]'
        self.word_separators = r'[\s,，、]+'
    
    def extract_word_level_timing(self, segments: List[TimedSegment]) -> List[TimedSegment]:
        """
        提取词级时序数据
        
        Args:
            segments: 原始片段列表
            
        Returns:
            List[TimedSegment]: 词级时序片段列表
            
        Raises:
            TimingProcessorError: 提取失败
        """
        if not segments:
            return []
        
        try:
            word_segments = []
            
            for segment in segments:
                # 分割文本为单词
                words = self._split_text_to_words(segment.original_text)
                if not words:
                    continue
                
                # 计算每个单词的时间分配
                segment_duration = segment.end_time - segment.start_time
                word_duration = segment_duration / len(words)
                
                current_time = segment.start_time
                
                for i, word in enumerate(words):
                    word_start = current_time
                    word_end = current_time + word_duration
                    
                    # 确保最后一个单词的结束时间与片段结束时间一致
                    if i == len(words) - 1:
                        word_end = segment.end_time
                    
                    word_segment = TimedSegment(
                        start_time=word_start,
                        end_time=word_end,
                        original_text=word.strip(),
                        confidence=segment.confidence,
                        speaker_id=segment.speaker_id
                    )
                    
                    word_segments.append(word_segment)
                    current_time = word_end
            
            return word_segments
            
        except Exception as e:
            raise TimingProcessorError(f"词级时序提取失败: {str(e)}")
    
    def identify_speakers(self, segments: List[TimedSegment], 
                         use_silence_detection: bool = True) -> List[TimedSegment]:
        """
        实现说话人识别功能
        
        Args:
            segments: 输入片段列表
            use_silence_detection: 是否使用静音检测
            
        Returns:
            List[TimedSegment]: 带有说话人标识的片段列表
            
        Raises:
            TimingProcessorError: 说话人识别失败
        """
        if not segments:
            return []
        
        try:
            identified_segments = []
            current_speaker_id = "speaker_1"
            speaker_counter = 1
            
            for i, segment in enumerate(segments):
                # 复制片段
                new_segment = TimedSegment(
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    original_text=segment.original_text,
                    confidence=segment.confidence,
                    speaker_id=current_speaker_id
                )
                
                # 说话人切换检测
                if i > 0:
                    prev_segment = segments[i - 1]
                    gap_duration = segment.start_time - prev_segment.end_time
                    
                    # 基于静音间隔判断说话人切换
                    if use_silence_detection and gap_duration > self.speaker_change_threshold:
                        speaker_counter += 1
                        current_speaker_id = f"speaker_{speaker_counter}"
                        new_segment.speaker_id = current_speaker_id
                    
                    # 基于文本特征判断说话人切换
                    elif self._detect_speaker_change_by_text(prev_segment, segment):
                        speaker_counter += 1
                        current_speaker_id = f"speaker_{speaker_counter}"
                        new_segment.speaker_id = current_speaker_id
                
                identified_segments.append(new_segment)
            
            return identified_segments
            
        except Exception as e:
            raise TimingProcessorError(f"说话人识别失败: {str(e)}")
    
    def calculate_confidence_scores(self, segments: List[TimedSegment]) -> Dict[str, float]:
        """
        生成置信度分数用于质量评估
        
        Args:
            segments: 片段列表
            
        Returns:
            Dict[str, float]: 置信度统计信息
            
        Raises:
            TimingProcessorError: 置信度计算失败
        """
        if not segments:
            return {
                'average_confidence': 0.0,
                'high_confidence_ratio': 0.0,
                'medium_confidence_ratio': 0.0,
                'low_confidence_ratio': 0.0,
                'total_segments': 0
            }
        
        try:
            confidences = [seg.confidence for seg in segments if seg.confidence is not None]
            
            if not confidences:
                return {
                    'average_confidence': 0.0,
                    'high_confidence_ratio': 0.0,
                    'medium_confidence_ratio': 0.0,
                    'low_confidence_ratio': 0.0,
                    'total_segments': len(segments)
                }
            
            # 计算平均置信度
            average_confidence = sum(confidences) / len(confidences)
            
            # 分类置信度等级
            high_count = sum(1 for c in confidences if c >= self.confidence_thresholds['high'])
            medium_count = sum(1 for c in confidences 
                             if self.confidence_thresholds['medium'] <= c < self.confidence_thresholds['high'])
            low_count = sum(1 for c in confidences if c < self.confidence_thresholds['medium'])
            
            total = len(confidences)
            
            return {
                'average_confidence': average_confidence,
                'high_confidence_ratio': high_count / total,
                'medium_confidence_ratio': medium_count / total,
                'low_confidence_ratio': low_count / total,
                'total_segments': len(segments)
            }
            
        except Exception as e:
            raise TimingProcessorError(f"置信度计算失败: {str(e)}")
    
    def analyze_timing_quality(self, segments: List[TimedSegment]) -> TimingQualityMetrics:
        """
        分析时序质量
        
        Args:
            segments: 片段列表
            
        Returns:
            TimingQualityMetrics: 时序质量指标
            
        Raises:
            TimingProcessorError: 质量分析失败
        """
        if not segments:
            return TimingQualityMetrics(
                total_segments=0,
                average_segment_duration=0.0,
                confidence_distribution={'high': 0, 'medium': 0, 'low': 0},
                speaker_distribution={},
                gaps_count=0,
                overlaps_count=0,
                total_speech_time=0.0,
                total_silence_time=0.0
            )
        
        try:
            # 基本统计
            total_segments = len(segments)
            segment_durations = [seg.end_time - seg.start_time for seg in segments]
            average_segment_duration = sum(segment_durations) / len(segment_durations)
            
            # 置信度分布
            confidence_dist = {'high': 0, 'medium': 0, 'low': 0}
            for seg in segments:
                if seg.confidence is not None:
                    if seg.confidence >= self.confidence_thresholds['high']:
                        confidence_dist['high'] += 1
                    elif seg.confidence >= self.confidence_thresholds['medium']:
                        confidence_dist['medium'] += 1
                    else:
                        confidence_dist['low'] += 1
            
            # 说话人分布
            speaker_dist = {}
            for seg in segments:
                if seg.speaker_id:
                    speaker_dist[seg.speaker_id] = speaker_dist.get(seg.speaker_id, 0) + 1
            
            # 间隙和重叠分析
            gaps_count = 0
            overlaps_count = 0
            total_silence_time = 0.0
            
            for i in range(1, len(segments)):
                prev_seg = segments[i - 1]
                curr_seg = segments[i]
                
                gap = curr_seg.start_time - prev_seg.end_time
                
                if gap > 0.1:  # 大于100ms的间隙
                    gaps_count += 1
                    total_silence_time += gap
                elif gap < -0.05:  # 重叠超过50ms
                    overlaps_count += 1
            
            # 总语音时间
            total_speech_time = sum(segment_durations)
            
            return TimingQualityMetrics(
                total_segments=total_segments,
                average_segment_duration=average_segment_duration,
                confidence_distribution=confidence_dist,
                speaker_distribution=speaker_dist,
                gaps_count=gaps_count,
                overlaps_count=overlaps_count,
                total_speech_time=total_speech_time,
                total_silence_time=total_silence_time
            )
            
        except Exception as e:
            raise TimingProcessorError(f"时序质量分析失败: {str(e)}")
    
    def get_speaker_statistics(self, segments: List[TimedSegment]) -> List[SpeakerStats]:
        """
        获取说话人统计信息
        
        Args:
            segments: 片段列表
            
        Returns:
            List[SpeakerStats]: 说话人统计列表
            
        Raises:
            TimingProcessorError: 统计失败
        """
        if not segments:
            return []
        
        try:
            speaker_data = {}
            
            for segment in segments:
                speaker_id = segment.speaker_id or "unknown"
                
                if speaker_id not in speaker_data:
                    speaker_data[speaker_id] = {
                        'total_duration': 0.0,
                        'segment_count': 0,
                        'confidences': [],
                        'word_count': 0
                    }
                
                data = speaker_data[speaker_id]
                data['total_duration'] += segment.end_time - segment.start_time
                data['segment_count'] += 1
                
                if segment.confidence is not None:
                    data['confidences'].append(segment.confidence)
                
                # 统计单词数
                words = self._split_text_to_words(segment.original_text)
                data['word_count'] += len(words)
            
            # 生成统计结果
            stats = []
            for speaker_id, data in speaker_data.items():
                avg_confidence = (sum(data['confidences']) / len(data['confidences'])) \
                    if data['confidences'] else 0.0
                
                stat = SpeakerStats(
                    speaker_id=speaker_id,
                    total_duration=data['total_duration'],
                    segment_count=data['segment_count'],
                    average_confidence=avg_confidence,
                    word_count=data['word_count']
                )
                stats.append(stat)
            
            # 按发言时长排序
            stats.sort(key=lambda x: x.total_duration, reverse=True)
            
            return stats
            
        except Exception as e:
            raise TimingProcessorError(f"说话人统计失败: {str(e)}")
    
    def merge_adjacent_segments(self, segments: List[TimedSegment], 
                              max_gap: float = 0.2) -> List[TimedSegment]:
        """
        合并相邻的短片段
        
        Args:
            segments: 输入片段列表
            max_gap: 最大允许间隙（秒）
            
        Returns:
            List[TimedSegment]: 合并后的片段列表
            
        Raises:
            TimingProcessorError: 合并失败
        """
        if not segments:
            return []
        
        try:
            merged_segments = []
            current_segment = segments[0]
            
            for i in range(1, len(segments)):
                next_segment = segments[i]
                
                # 检查是否可以合并
                gap = next_segment.start_time - current_segment.end_time
                same_speaker = current_segment.speaker_id == next_segment.speaker_id
                
                if gap <= max_gap and same_speaker:
                    # 合并片段
                    current_segment = TimedSegment(
                        start_time=current_segment.start_time,
                        end_time=next_segment.end_time,
                        original_text=current_segment.original_text + " " + next_segment.original_text,
                        confidence=min(current_segment.confidence or 0, next_segment.confidence or 0),
                        speaker_id=current_segment.speaker_id
                    )
                else:
                    # 添加当前片段并开始新片段
                    merged_segments.append(current_segment)
                    current_segment = next_segment
            
            # 添加最后一个片段
            merged_segments.append(current_segment)
            
            return merged_segments
            
        except Exception as e:
            raise TimingProcessorError(f"片段合并失败: {str(e)}")
    
    def filter_by_confidence(self, segments: List[TimedSegment], 
                           min_confidence: float) -> List[TimedSegment]:
        """
        按置信度过滤片段
        
        Args:
            segments: 输入片段列表
            min_confidence: 最小置信度阈值
            
        Returns:
            List[TimedSegment]: 过滤后的片段列表
        """
        return [seg for seg in segments 
                if seg.confidence is not None and seg.confidence >= min_confidence]
    
    def _split_text_to_words(self, text: str) -> List[str]:
        """分割文本为单词"""
        if not text:
            return []
        
        # 移除多余的空白字符
        text = text.strip()
        
        # 分割为单词（支持中英文）
        words = re.split(self.word_separators, text)
        
        # 过滤空字符串
        words = [word for word in words if word.strip()]
        
        return words
    
    def _detect_speaker_change_by_text(self, prev_segment: TimedSegment, 
                                     curr_segment: TimedSegment) -> bool:
        """基于文本特征检测说话人切换"""
        # 检查句子结束标记
        if re.search(self.sentence_endings, prev_segment.original_text):
            return True
        
        # 检查语调变化（简单实现）
        prev_text = prev_segment.original_text.lower()
        curr_text = curr_segment.original_text.lower()
        
        # 检查问句转换
        if '?' in prev_text or '？' in prev_text:
            return True
        
        return False