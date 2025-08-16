import threading
import time
from typing import Callable, Optional, Dict, Any
from datetime import datetime
from models.core import Job, JobStatus, ProcessingStage, ProcessingResult
from services.job_manager import JobManager
from services.thread_manager import ThreadManager


class ProcessingPipelineError(Exception):
    """处理管道错误"""
    pass


class ProcessingPipeline:
    """
    处理管道核心架构
    
    负责协调整个音视频翻译流程，管理各个处理阶段的顺序执行，
    提供进度回调机制和统一的错误处理。
    """
    
    def __init__(self, job_manager: JobManager, max_concurrent_jobs: int = 3):
        self.job_manager = job_manager
        self.thread_manager = ThreadManager(job_manager, max_concurrent_jobs)
        self._shutdown = False
        self._lock = threading.Lock()
        
        # 处理阶段定义
        self._processing_stages = [
            ProcessingStage.EXTRACTING_AUDIO,
            ProcessingStage.TRANSCRIBING,
            ProcessingStage.TRANSLATING,
            ProcessingStage.SYNTHESIZING,
            ProcessingStage.SYNCHRONIZING,
            ProcessingStage.FINALIZING
        ]
    
    def process_file(self, job: Job) -> ProcessingResult:
        """
        处理文件的主要入口点
        
        Args:
            job: 要处理的作业对象
            
        Returns:
            ProcessingResult: 处理结果
        """
        start_time = time.time()
        stages_completed = []
        
        try:
            # 更新作业状态为处理中
            self.job_manager.update_progress(job.id, ProcessingStage.EXTRACTING_AUDIO, 0.0)
            
            # 逐个执行处理阶段
            for i, stage in enumerate(self._processing_stages):
                if self._shutdown:
                    raise ProcessingPipelineError("处理管道已关闭")
                
                # 计算当前阶段的进度百分比
                stage_progress = (i / len(self._processing_stages)) * 100
                
                # 更新作业进度
                self.job_manager.update_progress(job.id, stage, stage_progress)
                
                # 执行当前阶段（这里是占位符实现）
                self._execute_stage(job, stage)
                stages_completed.append(stage)
                
                # 模拟处理时间
                time.sleep(0.1)
            
            # 标记完成
            self.job_manager.update_progress(job.id, ProcessingStage.COMPLETED, 100.0)
            stages_completed.append(ProcessingStage.COMPLETED)
            
            processing_time = time.time() - start_time
            
            # 生成输出文件路径（占位符实现）
            output_path = self._generate_output_path(job.input_file_path, job.target_language)
            self.job_manager.update_job_output(job.id, output_path)
            
            return ProcessingResult(
                success=True,
                output_path=output_path,
                processing_time=processing_time,
                stages_completed=stages_completed
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_message = str(e)
            
            # 更新作业错误状态
            self.job_manager.update_job_error(job.id, error_message)
            
            return ProcessingResult(
                success=False,
                error_message=error_message,
                processing_time=processing_time,
                stages_completed=stages_completed
            )
    
    def process_file_async(self, job: Job, completion_callback: Optional[Callable[[ProcessingResult], None]] = None) -> str:
        """
        异步处理文件
        
        Args:
            job: 要处理的作业对象
            completion_callback: 完成时的回调函数
            
        Returns:
            线程ID
        """
        def _process_with_callback(job: Job) -> ProcessingResult:
            try:
                result = self.process_file(job)
                if completion_callback:
                    completion_callback(result)
                return result
            except Exception as e:
                error_result = ProcessingResult(
                    success=False,
                    error_message=str(e),
                    processing_time=0.0,
                    stages_completed=[]
                )
                if completion_callback:
                    completion_callback(error_result)
                return error_result
        
        # 使用ThreadManager提交作业
        thread_id = self.thread_manager.submit_job(job, _process_with_callback)
        return thread_id
    
    def get_progress_callback(self, job_id: str) -> Callable[[ProcessingStage, float], None]:
        """
        获取进度回调函数
        
        Args:
            job_id: 作业ID
            
        Returns:
            进度回调函数
        """
        def progress_callback(stage: ProcessingStage, progress: float):
            """进度回调函数"""
            try:
                self.job_manager.update_progress(job_id, stage, progress)
            except Exception as e:
                print(f"更新进度失败: {e}")
        
        return progress_callback
    
    def handle_stage_error(self, job: Job, stage: ProcessingStage, error: Exception) -> None:
        """
        处理阶段错误
        
        Args:
            job: 作业对象
            stage: 出错的处理阶段
            error: 错误对象
        """
        error_message = f"阶段 {stage.value} 处理失败: {str(error)}"
        print(f"处理管道错误 - 作业 {job.id}: {error_message}")
        
        # 更新作业错误状态
        self.job_manager.update_job_error(job.id, error_message)
    
    def cancel_job(self, job_id: str) -> bool:
        """
        取消正在处理的作业
        
        Args:
            job_id: 作业ID
            
        Returns:
            是否成功取消
        """
        success = self.thread_manager.cancel_job_thread(job_id)
        if success:
            # 更新作业状态
            self.job_manager.update_job_error(job_id, "作业已取消")
        return success
    
    def get_active_jobs_count(self) -> int:
        """获取活跃作业数量"""
        return self.thread_manager.get_active_threads_count()
    
    def get_queue_size(self) -> int:
        """获取等待队列大小"""
        return self.thread_manager.get_queue_size()
    
    def get_thread_info(self) -> list:
        """获取所有线程信息"""
        return self.thread_manager.get_all_threads_info()
    
    def is_job_processing(self, job_id: str) -> bool:
        """检查作业是否正在处理中"""
        return self.thread_manager.is_job_processing(job_id)
    
    def shutdown(self) -> None:
        """关闭处理管道"""
        self._shutdown = True
        
        # 关闭线程管理器
        self.thread_manager.shutdown(timeout=10.0)
    
    def _execute_stage(self, job: Job, stage: ProcessingStage) -> None:
        """
        执行具体的处理阶段（占位符实现）
        
        Args:
            job: 作业对象
            stage: 处理阶段
        """
        # 这里是各个处理阶段的占位符实现
        # 在后续任务中会被具体的服务实现替换
        
        if stage == ProcessingStage.EXTRACTING_AUDIO:
            # 音频提取阶段
            print(f"执行音频提取 - 作业 {job.id}")
            
        elif stage == ProcessingStage.TRANSCRIBING:
            # 语音转文本阶段
            print(f"执行语音转录 - 作业 {job.id}")
            
        elif stage == ProcessingStage.TRANSLATING:
            # 文本翻译阶段
            print(f"执行文本翻译 - 作业 {job.id}")
            
        elif stage == ProcessingStage.SYNTHESIZING:
            # 语音合成阶段
            print(f"执行语音合成 - 作业 {job.id}")
            
        elif stage == ProcessingStage.SYNCHRONIZING:
            # 音频同步阶段
            print(f"执行音频同步 - 作业 {job.id}")
            
        elif stage == ProcessingStage.FINALIZING:
            # 最终处理阶段
            print(f"执行最终处理 - 作业 {job.id}")
        
        # 模拟处理时间
        time.sleep(0.1)
    
    def _generate_output_path(self, input_path: str, target_language: str) -> str:
        """
        生成输出文件路径（占位符实现）
        
        Args:
            input_path: 输入文件路径
            target_language: 目标语言
            
        Returns:
            输出文件路径
        """
        import os
        
        # 解析输入文件路径
        base_dir = os.path.dirname(input_path)
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        
        # 生成输出文件名
        output_filename = f"{name}_{target_language}_translated{ext}"
        output_path = os.path.join(base_dir, "output", output_filename)
        
        return output_path