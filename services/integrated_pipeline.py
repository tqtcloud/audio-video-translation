import os
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from models.core import Job, ProcessingStage, FileMetadata, TimedSegment, FileType
from services.job_manager import JobManager
from services.processing_pipeline import ProcessingPipeline
from utils.validation import FileValidator
from services.audio_extractor import AudioExtractor
from services.speech_to_text import SpeechToTextService
from services.translation_service import TranslationService
from services.text_to_speech import TextToSpeechService
from services.audio_synchronizer import AudioSynchronizer
from services.audio_optimizer import AudioOptimizer
from services.video_assembler import VideoAssembler
from services.output_generator import OutputGenerator, OutputConfig
from utils.error_handler import ErrorHandler, ErrorContext, handle_error
from utils.fault_tolerance import FaultToleranceManager, FaultToleranceConfig, FaultToleranceStrategy


class IntegratedPipelineError(Exception):
    """集成管道错误"""
    pass


@dataclass
class PipelineConfig:
    """管道配置"""
    # 服务配置
    target_language: str = "zh-CN"
    voice_model: str = "alloy"
    preserve_background_audio: bool = True
    
    # 输出配置
    output_config: Optional[OutputConfig] = None
    
    # 容错配置
    enable_fault_tolerance: bool = True
    max_retries: int = 3
    
    # 进度回调
    progress_callback: Optional[Callable[[str, float, str], None]] = None


@dataclass
class PipelineResult:
    """管道处理结果"""
    job_id: str
    success: bool
    output_file_path: Optional[str] = None
    processing_time: float = 0.0
    stages_completed: List[ProcessingStage] = None
    error_message: Optional[str] = None
    quality_metrics: Optional[Dict[str, Any]] = None


class IntegratedPipeline:
    """
    集成处理管道
    
    将所有服务组件集成到统一的处理管道中，
    实现阶段间的数据传递和状态管理，
    提供统一的进度跟踪和错误处理。
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """初始化集成管道"""
        self.config = config or PipelineConfig()
        
        # 初始化管理器
        self.job_manager = JobManager()
        self.error_handler = ErrorHandler()
        self.fault_tolerance_manager = FaultToleranceManager()
        
        # 初始化服务组件
        self._initialize_services()
        
        # 配置容错机制
        if self.config.enable_fault_tolerance:
            self._configure_fault_tolerance()
        
        # 处理中的作业
        self._active_jobs: Dict[str, threading.Thread] = {}
        self._job_lock = threading.RLock()
        
        # 初始化处理管道
        self.pipeline = ProcessingPipeline(
            job_manager=self.job_manager,
            progress_callback=self._internal_progress_callback
        )
        
        # 注册处理阶段
        self._register_pipeline_stages()
    
    def _initialize_services(self):
        """初始化所有服务组件"""
        try:
            self.file_validator = FileValidator()
            self.audio_extractor = AudioExtractor()
            self.speech_to_text = SpeechToTextService()
            self.translation_service = TranslationService()
            self.text_to_speech = TextToSpeechService()
            self.audio_synchronizer = AudioSynchronizer()
            self.audio_optimizer = AudioOptimizer()
            self.video_assembler = VideoAssembler()
            self.output_generator = OutputGenerator(self.config.output_config)
        except Exception as e:
            raise IntegratedPipelineError(f"服务初始化失败: {str(e)}")
    
    def _configure_fault_tolerance(self):
        """配置容错机制"""
        # 为各个服务配置容错策略
        services_config = {
            "file_validation": FaultToleranceConfig(
                strategy=FaultToleranceStrategy.RETRY,
                retry_config={"max_attempts": 2, "base_delay": 1.0}
            ),
            "audio_extraction": FaultToleranceConfig(
                strategy=FaultToleranceStrategy.RETRY,
                retry_config={"max_attempts": 3, "base_delay": 2.0}
            ),
            "speech_to_text": FaultToleranceConfig(
                strategy=FaultToleranceStrategy.CIRCUIT_BREAKER,
                circuit_breaker_config={"failure_threshold": 5, "timeout": 300.0}
            ),
            "translation": FaultToleranceConfig(
                strategy=FaultToleranceStrategy.CIRCUIT_BREAKER,
                circuit_breaker_config={"failure_threshold": 3, "timeout": 180.0}
            ),
            "text_to_speech": FaultToleranceConfig(
                strategy=FaultToleranceStrategy.RETRY,
                retry_config={"max_attempts": 3, "base_delay": 5.0}
            ),
            "audio_processing": FaultToleranceConfig(
                strategy=FaultToleranceStrategy.RETRY,
                retry_config={"max_attempts": 2, "base_delay": 1.0}
            ),
            "video_assembly": FaultToleranceConfig(
                strategy=FaultToleranceStrategy.RETRY,
                retry_config={"max_attempts": 2, "base_delay": 3.0}
            )
        }
        
        for service_name, config in services_config.items():
            self.fault_tolerance_manager.register_service(service_name, config)
    
    def _register_pipeline_stages(self):
        """注册管道处理阶段"""
        # 文件验证阶段
        self.pipeline.register_stage(
            ProcessingStage.FILE_VALIDATION,
            self._execute_file_validation
        )
        
        # 音频提取阶段
        self.pipeline.register_stage(
            ProcessingStage.AUDIO_EXTRACTION,
            self._execute_audio_extraction
        )
        
        # 语音转文本阶段
        self.pipeline.register_stage(
            ProcessingStage.SPEECH_TO_TEXT,
            self._execute_speech_to_text
        )
        
        # 文本翻译阶段
        self.pipeline.register_stage(
            ProcessingStage.TEXT_TRANSLATION,
            self._execute_text_translation
        )
        
        # 文本转语音阶段
        self.pipeline.register_stage(
            ProcessingStage.TEXT_TO_SPEECH,
            self._execute_text_to_speech
        )
        
        # 音频同步阶段
        self.pipeline.register_stage(
            ProcessingStage.AUDIO_SYNC,
            self._execute_audio_sync
        )
        
        # 视频组装阶段
        self.pipeline.register_stage(
            ProcessingStage.VIDEO_ASSEMBLY,
            self._execute_video_assembly
        )
        
        # 输出生成阶段
        self.pipeline.register_stage(
            ProcessingStage.OUTPUT_GENERATION,
            self._execute_output_generation
        )
    
    def process_file(self, file_path: str, target_language: Optional[str] = None) -> str:
        """
        处理文件
        
        Args:
            file_path: 输入文件路径
            target_language: 目标语言（可选）
            
        Returns:
            str: 作业ID
            
        Raises:
            IntegratedPipelineError: 处理失败
        """
        try:
            # 创建作业
            job = Job(
                file_path=file_path,
                target_language=target_language or self.config.target_language,
                created_at=time.time()
            )
            
            # 注册作业
            job_id = self.job_manager.create_job(job)
            
            # 在单独线程中启动处理
            thread = threading.Thread(
                target=self._process_job_async,
                args=(job_id,),
                name=f"ProcessingThread-{job_id}"
            )
            
            with self._job_lock:
                self._active_jobs[job_id] = thread
            
            thread.start()
            
            return job_id
            
        except Exception as e:
            error_context = ErrorContext(
                file_path=file_path,
                operation="process_file"
            )
            processed_error = handle_error(e, error_context)
            raise IntegratedPipelineError(processed_error.user_message)
    
    def _process_job_async(self, job_id: str):
        """异步处理作业"""
        try:
            # 执行管道处理
            result = self.pipeline.process_job(job_id)
            
            # 更新作业状态
            if result.success:
                self.job_manager.update_job_status(job_id, ProcessingStage.COMPLETED)
            else:
                self.job_manager.update_job_status(job_id, ProcessingStage.FAILED)
                
        except Exception as e:
            # 处理异常
            error_context = ErrorContext(
                job_id=job_id,
                operation="async_processing"
            )
            processed_error = handle_error(e, error_context)
            
            # 更新作业状态为失败
            self.job_manager.update_job_status(job_id, ProcessingStage.FAILED)
            
            # 记录错误信息
            job = self.job_manager.get_job(job_id)
            if job:
                job.error_message = processed_error.user_message
                
        finally:
            # 清理线程引用
            with self._job_lock:
                if job_id in self._active_jobs:
                    del self._active_jobs[job_id]
    
    def get_processing_result(self, job_id: str) -> PipelineResult:
        """获取处理结果"""
        job = self.job_manager.get_job(job_id)
        if not job:
            raise IntegratedPipelineError(f"作业不存在: {job_id}")
        
        # 构建结果
        result = PipelineResult(
            job_id=job_id,
            success=(job.current_stage == ProcessingStage.COMPLETED),
            processing_time=job.processing_time,
            stages_completed=self._get_completed_stages(job),
            error_message=getattr(job, 'error_message', None)
        )
        
        # 如果处理完成，获取输出路径
        if result.success and hasattr(job, 'output_file_path'):
            result.output_file_path = job.output_file_path
            
        # 如果有质量指标，添加到结果中
        if hasattr(job, 'quality_metrics'):
            result.quality_metrics = job.quality_metrics
        
        return result
    
    def _get_completed_stages(self, job: Job) -> List[ProcessingStage]:
        """获取已完成的阶段"""
        all_stages = [
            ProcessingStage.FILE_VALIDATION,
            ProcessingStage.AUDIO_EXTRACTION,
            ProcessingStage.SPEECH_TO_TEXT,
            ProcessingStage.TEXT_TRANSLATION,
            ProcessingStage.TEXT_TO_SPEECH,
            ProcessingStage.AUDIO_SYNC,
            ProcessingStage.VIDEO_ASSEMBLY,
            ProcessingStage.OUTPUT_GENERATION
        ]
        
        completed = []
        for stage in all_stages:
            if stage.value <= job.current_stage.value:
                completed.append(stage)
            else:
                break
        
        return completed
    
    def _internal_progress_callback(self, job_id: str, progress: float, message: str):
        """内部进度回调"""
        if self.config.progress_callback:
            self.config.progress_callback(job_id, progress, message)
    
    # 各个阶段的执行方法
    def _execute_file_validation(self, job: Job) -> Dict[str, Any]:
        """执行文件验证阶段"""
        def validate():
            # 验证文件
            validation_result = self.file_validator.validate_file(job.file_path)
            
            # 提取元数据
            metadata = self.file_validator.extract_metadata(job.file_path)
            
            return {
                "validation_result": validation_result,
                "metadata": metadata
            }
        
        if self.config.enable_fault_tolerance:
            return self.fault_tolerance_manager.execute_with_fault_tolerance(
                "file_validation", validate
            )
        else:
            return validate()
    
    def _execute_audio_extraction(self, job: Job) -> Dict[str, Any]:
        """执行音频提取阶段"""
        def extract():
            # 检查是否需要提取音频
            metadata = job.metadata
            if metadata.file_type == FileType.AUDIO:
                # 音频文件直接使用原文件
                return {
                    "audio_path": job.file_path,
                    "audio_properties": metadata.audio_properties
                }
            else:
                # 视频文件需要提取音频
                audio_path = self.audio_extractor.extract_audio(job.file_path)
                audio_properties = self.audio_extractor.get_audio_properties(audio_path)
                
                return {
                    "audio_path": audio_path,
                    "audio_properties": audio_properties
                }
        
        if self.config.enable_fault_tolerance:
            return self.fault_tolerance_manager.execute_with_fault_tolerance(
                "audio_extraction", extract
            )
        else:
            return extract()
    
    def _execute_speech_to_text(self, job: Job) -> Dict[str, Any]:
        """执行语音转文本阶段"""
        def transcribe():
            audio_path = job.intermediate_results["audio_extraction"]["audio_path"]
            
            # 执行语音转录
            transcription_result = self.speech_to_text.transcribe_audio(audio_path)
            
            return {
                "transcription": transcription_result.transcript,
                "segments": transcription_result.segments,
                "language": transcription_result.language,
                "confidence": transcription_result.confidence
            }
        
        if self.config.enable_fault_tolerance:
            return self.fault_tolerance_manager.execute_with_fault_tolerance(
                "speech_to_text", transcribe
            )
        else:
            return transcribe()
    
    def _execute_text_translation(self, job: Job) -> Dict[str, Any]:
        """执行文本翻译阶段"""
        def translate():
            segments = job.intermediate_results["speech_to_text"]["segments"]
            source_language = job.intermediate_results["speech_to_text"]["language"]
            
            # 翻译文本段落
            translated_segments = self.translation_service.translate_segments(
                segments, source_language, job.target_language
            )
            
            return {
                "translated_segments": translated_segments,
                "source_language": source_language,
                "target_language": job.target_language
            }
        
        if self.config.enable_fault_tolerance:
            return self.fault_tolerance_manager.execute_with_fault_tolerance(
                "translation", translate
            )
        else:
            return translate()
    
    def _execute_text_to_speech(self, job: Job) -> Dict[str, Any]:
        """执行文本转语音阶段"""
        def synthesize():
            translated_segments = job.intermediate_results["text_translation"]["translated_segments"]
            
            # 合成语音
            synthesis_result = self.text_to_speech.synthesize_segments(
                translated_segments,
                voice=self.config.voice_model,
                target_language=job.target_language
            )
            
            return {
                "synthesized_audio_path": synthesis_result.audio_file_path,
                "synthesis_quality": synthesis_result.quality_score,
                "total_duration": synthesis_result.total_duration
            }
        
        if self.config.enable_fault_tolerance:
            return self.fault_tolerance_manager.execute_with_fault_tolerance(
                "text_to_speech", synthesize
            )
        else:
            return synthesize()
    
    def _execute_audio_sync(self, job: Job) -> Dict[str, Any]:
        """执行音频同步阶段"""
        def sync():
            original_segments = job.intermediate_results["speech_to_text"]["segments"]
            translated_audio_path = job.intermediate_results["text_to_speech"]["synthesized_audio_path"]
            
            # 分析同步质量
            sync_analysis = self.audio_synchronizer.analyze_sync_quality(
                original_segments, translated_audio_path
            )
            
            # 如果需要调整
            if sync_analysis.sync_quality_score < 0.8:
                adjustment_result = self.audio_synchronizer.adjust_audio_timing(
                    translated_audio_path,
                    original_segments,
                    preserve_background=self.config.preserve_background_audio
                )
                optimized_audio_path = adjustment_result.adjusted_audio_path
            else:
                optimized_audio_path = translated_audio_path
            
            # 进一步优化
            optimization_result = self.audio_optimizer.optimize_audio_timing(
                optimized_audio_path,
                original_segments,
                preserve_background=self.config.preserve_background_audio
            )
            
            return {
                "final_audio_path": optimization_result.optimized_audio_path,
                "sync_analysis": sync_analysis,
                "optimization_result": optimization_result
            }
        
        if self.config.enable_fault_tolerance:
            return self.fault_tolerance_manager.execute_with_fault_tolerance(
                "audio_processing", sync
            )
        else:
            return sync()
    
    def _execute_video_assembly(self, job: Job) -> Dict[str, Any]:
        """执行视频组装阶段"""
        def assemble():
            final_audio_path = job.intermediate_results["audio_sync"]["final_audio_path"]
            metadata = job.metadata
            
            if metadata.file_type == FileType.VIDEO:
                # 视频文件：替换音频轨道
                replacement_result = self.video_assembler.replace_audio_track(
                    job.file_path,
                    final_audio_path,
                    preserve_quality=True
                )
                
                return {
                    "output_video_path": replacement_result.output_video_path,
                    "quality_preserved": replacement_result.quality_preserved,
                    "processing_info": replacement_result
                }
            else:
                # 音频文件：直接使用优化后的音频
                return {
                    "output_audio_path": final_audio_path,
                    "processing_info": None
                }
        
        if self.config.enable_fault_tolerance:
            return self.fault_tolerance_manager.execute_with_fault_tolerance(
                "video_assembly", assemble
            )
        else:
            return assemble()
    
    def _execute_output_generation(self, job: Job) -> Dict[str, Any]:
        """执行输出生成阶段"""
        def generate():
            video_assembly_result = job.intermediate_results["video_assembly"]
            final_audio_path = job.intermediate_results["audio_sync"]["final_audio_path"]
            
            # 生成最终输出
            if "output_video_path" in video_assembly_result:
                # 视频输出
                output_result = self.output_generator.generate_video_output(
                    job.file_path,
                    final_audio_path
                )
            else:
                # 音频输出
                output_result = self.output_generator.generate_audio_output(
                    job.file_path,
                    final_audio_path
                )
            
            # 设置作业的输出路径
            job.output_file_path = output_result.output_path
            
            return {
                "output_result": output_result,
                "final_output_path": output_result.output_path
            }
        
        return generate()  # 输出生成不需要容错机制
    
    def get_job_status(self, job_id: str) -> Optional[Job]:
        """获取作业状态"""
        return self.job_manager.get_job(job_id)
    
    def list_active_jobs(self) -> List[str]:
        """列出活跃作业"""
        with self._job_lock:
            return list(self._active_jobs.keys())
    
    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        with self._job_lock:
            if job_id in self._active_jobs:
                # 这里可以实现更复杂的取消逻辑
                # 目前只是标记作业为已取消
                self.job_manager.update_job_status(job_id, ProcessingStage.FAILED)
                return True
            return False
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标"""
        return {
            "active_jobs_count": len(self._active_jobs),
            "total_jobs_processed": len(self.job_manager.jobs),
            "fault_tolerance_metrics": self.fault_tolerance_manager.get_all_metrics(),
            "error_statistics": self.error_handler.get_error_statistics()
        }
    
    def shutdown(self):
        """关闭管道"""
        # 等待所有活跃作业完成或超时
        with self._job_lock:
            active_threads = list(self._active_jobs.values())
        
        for thread in active_threads:
            thread.join(timeout=30)  # 最多等待30秒
        
        # 关闭容错管理器
        self.fault_tolerance_manager.shutdown()
        
        # 清理资源
        self._active_jobs.clear()