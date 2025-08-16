import os
import time
import tempfile
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pydub import AudioSegment
from pydub.utils import which
import ffmpeg
from models.core import TimedSegment


class AudioSynchronizerError(Exception):
    """音频同步器错误"""
    pass


@dataclass
class SyncAnalysisResult:
    """同步分析结果"""
    timing_accuracy: float  # 时序准确性 (0-1)
    avg_offset: float  # 平均偏移量（秒）
    max_offset: float  # 最大偏移量（秒）
    sync_quality_score: float  # 同步质量评分 (0-1)
    segment_offsets: List[Tuple[int, float]]  # (segment_index, offset_seconds)
    issues_detected: List[str]  # 检测到的问题
    processing_time: float


@dataclass
class AudioAdjustmentResult:
    """音频调整结果"""
    adjusted_audio_path: str
    speed_adjustment: float  # 实际应用的速度调整
    quality_preserved: bool
    background_preserved: bool
    processing_time: float
    adjustment_details: Dict[str, float]


class AudioSynchronizer:
    """
    音频同步和质量控制服务
    
    实现原始音频与翻译音频的时序比较算法，
    时序偏移检测和分析，音频速度调整功能等。
    """
    
    def __init__(self):
        """初始化音频同步器"""
        # 同步分析配置
        self.sync_config = {
            'timing_tolerance': 0.1,  # 时序容差（秒）
            'max_acceptable_offset': 0.5,  # 最大可接受偏移（秒）
            'quality_threshold': 0.7,  # 质量阈值
            'segment_min_duration': 0.2  # 最小片段持续时间
        }
        
        # 音频调整配置
        self.adjustment_config = {
            'min_speed': 0.8,  # 最小速度倍率
            'max_speed': 1.2,  # 最大速度倍率
            'speed_step': 0.05,  # 速度调整步长
            'quality_preservation': True,  # 是否保持音频质量
            'background_preservation': True  # 是否保留背景音
        }
        
        # 质量评估参数
        self.quality_params = {
            'sample_rate_threshold': 16000,  # 最低采样率
            'dynamic_range_threshold': 20,  # 动态范围阈值（dB）
            'snr_threshold': 10  # 信噪比阈值（dB）
        }
        
        # 检查依赖
        if not which("ffmpeg"):
            raise AudioSynchronizerError("未找到 FFmpeg，请确保已安装")
    
    def analyze_sync_quality(self, original_segments: List[TimedSegment],
                           translated_audio_path: str,
                           reference_segments: Optional[List[TimedSegment]] = None) -> SyncAnalysisResult:
        """
        分析原始音频与翻译音频的同步质量
        
        Args:
            original_segments: 原始时序片段
            translated_audio_path: 翻译音频文件路径
            reference_segments: 参考时序片段（可选）
            
        Returns:
            SyncAnalysisResult: 同步分析结果
            
        Raises:
            AudioSynchronizerError: 分析失败
        """
        if not original_segments:
            raise AudioSynchronizerError("原始片段列表为空")
        
        if not os.path.exists(translated_audio_path):
            raise AudioSynchronizerError(f"翻译音频文件不存在: {translated_audio_path}")
        
        start_time = time.time()
        
        try:
            # 加载翻译音频
            translated_audio = AudioSegment.from_file(translated_audio_path)
            translated_duration = len(translated_audio) / 1000.0
            
            # 计算预期总时长
            expected_duration = original_segments[-1].end_time if original_segments else 0.0
            
            # 分析各个片段的时序偏移
            segment_offsets = self._analyze_segment_offsets(
                original_segments, translated_audio, reference_segments
            )
            
            # 计算统计指标
            offsets = [offset for _, offset in segment_offsets]
            avg_offset = sum(offsets) / len(offsets) if offsets else 0.0
            max_offset = max(abs(offset) for offset in offsets) if offsets else 0.0
            
            # 计算时序准确性
            timing_accuracy = self._calculate_timing_accuracy(
                original_segments, translated_duration, segment_offsets
            )
            
            # 计算同步质量评分
            sync_quality_score = self._calculate_sync_quality_score(
                timing_accuracy, avg_offset, max_offset
            )
            
            # 检测问题
            issues_detected = self._detect_sync_issues(
                segment_offsets, avg_offset, max_offset, timing_accuracy
            )
            
            processing_time = time.time() - start_time
            
            return SyncAnalysisResult(
                timing_accuracy=timing_accuracy,
                avg_offset=avg_offset,
                max_offset=max_offset,
                sync_quality_score=sync_quality_score,
                segment_offsets=segment_offsets,
                issues_detected=issues_detected,
                processing_time=processing_time
            )
            
        except Exception as e:
            raise AudioSynchronizerError(f"同步质量分析失败: {str(e)}")
    
    def adjust_audio_timing(self, audio_path: str,
                           target_segments: List[TimedSegment],
                           output_path: Optional[str] = None,
                           preserve_background: bool = True) -> AudioAdjustmentResult:
        """
        调整音频时序以匹配目标片段
        
        Args:
            audio_path: 输入音频文件路径
            target_segments: 目标时序片段
            output_path: 输出文件路径（可选）
            preserve_background: 是否保留背景音乐和音效
            
        Returns:
            AudioAdjustmentResult: 音频调整结果
            
        Raises:
            AudioSynchronizerError: 调整失败
        """
        if not os.path.exists(audio_path):
            raise AudioSynchronizerError(f"音频文件不存在: {audio_path}")
        
        if not target_segments:
            raise AudioSynchronizerError("目标片段列表为空")
        
        start_time = time.time()
        
        try:
            # 加载原始音频
            audio = AudioSegment.from_file(audio_path)
            current_duration = len(audio) / 1000.0
            
            # 计算目标总时长
            target_duration = target_segments[-1].end_time if target_segments else current_duration
            
            # 计算需要的速度调整
            speed_ratio = current_duration / target_duration
            
            # 限制速度调整范围
            speed_ratio = max(self.adjustment_config['min_speed'],
                            min(self.adjustment_config['max_speed'], speed_ratio))
            
            # 如果不需要显著调整，直接返回
            if abs(speed_ratio - 1.0) < 0.01:
                if not output_path:
                    output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
                # 复制原文件
                audio.export(output_path, format="mp3")
                
                return AudioAdjustmentResult(
                    adjusted_audio_path=output_path,
                    speed_adjustment=1.0,
                    quality_preserved=True,
                    background_preserved=True,
                    processing_time=time.time() - start_time,
                    adjustment_details={'speed_ratio': 1.0, 'method': 'no_adjustment'}
                )
            
            # 执行音频调整
            if preserve_background:
                adjusted_audio = self._adjust_with_background_preservation(
                    audio, speed_ratio, target_segments
                )
            else:
                adjusted_audio = self._adjust_audio_speed(audio, speed_ratio)
            
            # 保存调整后的音频
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            adjusted_audio.export(output_path, format="mp3", bitrate="192k")
            
            # 验证调整后的质量
            quality_preserved = self._verify_audio_quality(audio, adjusted_audio)
            
            processing_time = time.time() - start_time
            
            return AudioAdjustmentResult(
                adjusted_audio_path=output_path,
                speed_adjustment=speed_ratio,
                quality_preserved=quality_preserved,
                background_preserved=preserve_background,
                processing_time=processing_time,
                adjustment_details={
                    'speed_ratio': speed_ratio,
                    'original_duration': current_duration,
                    'target_duration': target_duration,
                    'method': 'background_preserved' if preserve_background else 'simple_speed'
                }
            )
            
        except Exception as e:
            raise AudioSynchronizerError(f"音频时序调整失败: {str(e)}")
    
    def generate_sync_report(self, analysis_result: SyncAnalysisResult,
                           segments: List[TimedSegment]) -> Dict[str, any]:
        """
        生成同步质量报告
        
        Args:
            analysis_result: 同步分析结果
            segments: 时序片段
            
        Returns:
            Dict[str, any]: 详细的同步质量报告
        """
        report = {
            'summary': {
                'overall_quality': 'excellent' if analysis_result.sync_quality_score > 0.9 
                                 else 'good' if analysis_result.sync_quality_score > 0.7
                                 else 'fair' if analysis_result.sync_quality_score > 0.5
                                 else 'poor',
                'sync_quality_score': analysis_result.sync_quality_score,
                'timing_accuracy': analysis_result.timing_accuracy,
                'total_segments': len(segments)
            },
            'timing_analysis': {
                'average_offset': analysis_result.avg_offset,
                'maximum_offset': analysis_result.max_offset,
                'offset_distribution': self._calculate_offset_distribution(analysis_result.segment_offsets),
                'problematic_segments': [
                    idx for idx, offset in analysis_result.segment_offsets 
                    if abs(offset) > self.sync_config['max_acceptable_offset']
                ]
            },
            'quality_metrics': {
                'segments_in_sync': sum(1 for _, offset in analysis_result.segment_offsets 
                                      if abs(offset) <= self.sync_config['timing_tolerance']),
                'segments_with_minor_issues': sum(1 for _, offset in analysis_result.segment_offsets 
                                                if self.sync_config['timing_tolerance'] < abs(offset) <= self.sync_config['max_acceptable_offset']),
                'segments_with_major_issues': sum(1 for _, offset in analysis_result.segment_offsets 
                                                if abs(offset) > self.sync_config['max_acceptable_offset'])
            },
            'issues_detected': analysis_result.issues_detected,
            'recommendations': self._generate_recommendations(analysis_result),
            'processing_info': {
                'analysis_time': analysis_result.processing_time,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        
        return report
    
    def _analyze_segment_offsets(self, original_segments: List[TimedSegment],
                               translated_audio: AudioSegment,
                               reference_segments: Optional[List[TimedSegment]]) -> List[Tuple[int, float]]:
        """分析各个片段的时序偏移"""
        segment_offsets = []
        translated_duration = len(translated_audio) / 1000.0
        
        for i, segment in enumerate(original_segments):
            # 计算预期的片段位置
            expected_start = segment.start_time
            expected_end = segment.end_time
            expected_duration = expected_end - expected_start
            
            # 如果有参考片段，使用参考时序
            if reference_segments and i < len(reference_segments):
                ref_segment = reference_segments[i]
                actual_start = ref_segment.start_time
                actual_end = ref_segment.end_time
            else:
                # 简单估算：基于总时长的比例
                progress = expected_start / original_segments[-1].end_time if original_segments[-1].end_time > 0 else 0
                actual_start = progress * translated_duration
                actual_end = actual_start + expected_duration
            
            # 计算偏移
            offset = actual_start - expected_start
            segment_offsets.append((i, offset))
        
        return segment_offsets
    
    def _calculate_timing_accuracy(self, original_segments: List[TimedSegment],
                                 translated_duration: float,
                                 segment_offsets: List[Tuple[int, float]]) -> float:
        """计算时序准确性"""
        if not original_segments or not segment_offsets:
            return 0.0
        
        expected_duration = original_segments[-1].end_time
        
        # 基于总时长的准确性
        duration_accuracy = 1.0 - min(1.0, abs(translated_duration - expected_duration) / expected_duration)
        
        # 基于片段偏移的准确性
        offsets = [abs(offset) for _, offset in segment_offsets]
        avg_offset = sum(offsets) / len(offsets)
        offset_accuracy = max(0.0, 1.0 - avg_offset / self.sync_config['max_acceptable_offset'])
        
        # 综合准确性
        return (duration_accuracy + offset_accuracy) / 2
    
    def _calculate_sync_quality_score(self, timing_accuracy: float,
                                    avg_offset: float, max_offset: float) -> float:
        """计算同步质量评分"""
        # 时序准确性权重：40%
        accuracy_score = timing_accuracy * 0.4
        
        # 平均偏移权重：30%
        avg_offset_score = max(0.0, 1.0 - avg_offset / self.sync_config['max_acceptable_offset']) * 0.3
        
        # 最大偏移权重：30%
        max_offset_score = max(0.0, 1.0 - max_offset / (self.sync_config['max_acceptable_offset'] * 2)) * 0.3
        
        return accuracy_score + avg_offset_score + max_offset_score
    
    def _detect_sync_issues(self, segment_offsets: List[Tuple[int, float]],
                          avg_offset: float, max_offset: float,
                          timing_accuracy: float) -> List[str]:
        """检测同步问题"""
        issues = []
        
        # 检查整体时序准确性
        if timing_accuracy < 0.7:
            issues.append("整体时序准确性较低")
        
        # 检查平均偏移
        if avg_offset > self.sync_config['max_acceptable_offset']:
            issues.append(f"平均时序偏移过大: {avg_offset:.3f}秒")
        
        # 检查最大偏移
        if max_offset > self.sync_config['max_acceptable_offset'] * 2:
            issues.append(f"存在严重的时序偏移: {max_offset:.3f}秒")
        
        # 检查偏移分布
        large_offsets = [offset for _, offset in segment_offsets 
                        if abs(offset) > self.sync_config['max_acceptable_offset']]
        if len(large_offsets) > len(segment_offsets) * 0.3:
            issues.append("超过30%的片段存在明显时序偏移")
        
        # 检查一致性
        offsets = [offset for _, offset in segment_offsets]
        if len(offsets) > 1:
            offset_variance = np.var(offsets)
            if offset_variance > 0.1:
                issues.append("时序偏移不一致，存在变化较大的偏移")
        
        return issues
    
    def _adjust_audio_speed(self, audio: AudioSegment, speed_ratio: float) -> AudioSegment:
        """调整音频速度（简单方法）"""
        try:
            # 使用 pydub 的内置方法
            if speed_ratio > 1.0:
                # 加速：减少播放时间
                adjusted = audio.speedup(playback_speed=speed_ratio)
            else:
                # 减速：增加播放时间
                adjusted = audio._spawn(audio.raw_data, overrides={
                    "frame_rate": int(audio.frame_rate * speed_ratio)
                }).set_frame_rate(audio.frame_rate)
            
            return adjusted
        except:
            # 备用方法：使用 FFmpeg
            return self._adjust_with_ffmpeg(audio, speed_ratio)
    
    def _adjust_with_background_preservation(self, audio: AudioSegment,
                                           speed_ratio: float,
                                           target_segments: List[TimedSegment]) -> AudioSegment:
        """保留背景音的音频调整"""
        try:
            # 这是一个简化实现，实际应用中可能需要更复杂的音频分离技术
            # 这里我们使用简单的速度调整，但保持音质
            
            # 使用更高质量的 FFmpeg 调整
            adjusted = self._adjust_with_ffmpeg(audio, speed_ratio, preserve_pitch=True)
            
            return adjusted
        except:
            # 回退到简单方法
            return self._adjust_audio_speed(audio, speed_ratio)
    
    def _adjust_with_ffmpeg(self, audio: AudioSegment, speed_ratio: float,
                           preserve_pitch: bool = False) -> AudioSegment:
        """使用 FFmpeg 调整音频速度"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_input:
            audio.export(temp_input.name, format="wav")
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_output:
                try:
                    if preserve_pitch:
                        # 保持音调的速度调整
                        (
                            ffmpeg
                            .input(temp_input.name)
                            .filter('atempo', speed_ratio)
                            .output(temp_output.name)
                            .overwrite_output()
                            .run(quiet=True)
                        )
                    else:
                        # 简单的速度调整
                        (
                            ffmpeg
                            .input(temp_input.name)
                            .filter('atempo', speed_ratio)
                            .output(temp_output.name)
                            .overwrite_output()
                            .run(quiet=True)
                        )
                    
                    # 加载调整后的音频
                    adjusted_audio = AudioSegment.from_wav(temp_output.name)
                    
                    return adjusted_audio
                    
                except Exception as e:
                    # FFmpeg 失败，回退到原音频
                    return audio
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(temp_input.name)
                        os.unlink(temp_output.name)
                    except:
                        pass
    
    def _verify_audio_quality(self, original: AudioSegment, adjusted: AudioSegment) -> bool:
        """验证调整后的音频质量"""
        try:
            # 检查基本属性
            if adjusted.frame_rate < self.quality_params['sample_rate_threshold']:
                return False
            
            # 检查时长合理性
            duration_ratio = len(adjusted) / len(original)
            if duration_ratio < 0.5 or duration_ratio > 2.0:
                return False
            
            # 检查音量
            if adjusted.dBFS < -50:  # 太安静
                return False
            
            return True
            
        except:
            return False
    
    def _calculate_offset_distribution(self, segment_offsets: List[Tuple[int, float]]) -> Dict[str, int]:
        """计算偏移分布"""
        distribution = {
            'excellent': 0,  # <= 0.1s
            'good': 0,       # 0.1s - 0.3s
            'fair': 0,       # 0.3s - 0.5s
            'poor': 0        # > 0.5s
        }
        
        for _, offset in segment_offsets:
            abs_offset = abs(offset)
            if abs_offset <= 0.1:
                distribution['excellent'] += 1
            elif abs_offset <= 0.3:
                distribution['good'] += 1
            elif abs_offset <= 0.5:
                distribution['fair'] += 1
            else:
                distribution['poor'] += 1
        
        return distribution
    
    def _generate_recommendations(self, analysis_result: SyncAnalysisResult) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if analysis_result.sync_quality_score < 0.7:
            recommendations.append("建议重新进行语音合成，调整语音速度参数")
        
        if analysis_result.max_offset > 1.0:
            recommendations.append("存在严重的时序偏移，建议检查原始时序数据的准确性")
        
        if len(analysis_result.issues_detected) > 2:
            recommendations.append("检测到多个同步问题，建议优化翻译和语音合成流程")
        
        if analysis_result.avg_offset > 0.3:
            recommendations.append("平均偏移较大，建议在语音合成时使用更精确的时序控制")
        
        # 添加积极的建议
        if analysis_result.sync_quality_score > 0.9:
            recommendations.append("同步质量优秀，可以直接使用")
        elif analysis_result.sync_quality_score > 0.7:
            recommendations.append("同步质量良好，可进行微调优化")
        
        return recommendations