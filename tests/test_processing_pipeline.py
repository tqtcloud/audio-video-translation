import os
import time
import tempfile
import shutil
import pytest
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock
from services.processing_pipeline import ProcessingPipeline, ProcessingPipelineError
from services.job_manager import JobManager
from models.core import Job, JobStatus, ProcessingStage, ProcessingResult


class TestProcessingPipeline:
    
    def setup_method(self):
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.job_state_file = os.path.join(self.temp_dir, "test_job_states.json")
        
        # 模拟配置
        with patch('services.job_manager.Config') as mock_config:
            config_instance = mock_config.return_value
            config_instance.SUPPORTED_LANGUAGES = ["en", "zh", "es", "fr", "de"]
            config_instance.JOB_STATE_FILE = self.job_state_file
            config_instance.JOB_STATE_SAVE_INTERVAL = 1
            
            self.job_manager = JobManager()
            self.pipeline = ProcessingPipeline(self.job_manager)
    
    def teardown_method(self):
        # 清理资源
        if hasattr(self, 'pipeline'):
            self.pipeline.shutdown()
        if hasattr(self, 'job_manager'):
            self.job_manager.shutdown()
        
        # 清理临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_process_file_success(self):
        """测试文件处理成功流程"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        result = self.pipeline.process_file(job)
        
        assert result.success is True
        assert result.output_path is not None
        assert result.error_message is None
        assert result.processing_time > 0
        assert len(result.stages_completed) == 7  # 6个处理阶段 + COMPLETED
        assert ProcessingStage.COMPLETED in result.stages_completed
        
        # 检查作业状态
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.progress == 100.0
        assert updated_job.output_file_path is not None
    
    def test_process_file_with_error(self):
        """测试处理过程中出现错误"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 模拟在执行阶段出现错误
        with patch.object(self.pipeline, '_execute_stage', side_effect=Exception("模拟错误")):
            result = self.pipeline.process_file(job)
        
        assert result.success is False
        assert result.output_path is None
        assert result.error_message == "模拟错误"
        assert result.processing_time > 0
        
        # 检查作业状态
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message == "模拟错误"
    
    def test_process_file_async(self):
        """测试异步文件处理"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 使用事件来同步测试
        completion_event = threading.Event()
        result_holder = {}
        
        def completion_callback(result):
            result_holder['result'] = result
            completion_event.set()
        
        # 启动异步处理
        self.pipeline.process_file_async(job, completion_callback)
        
        # 等待完成
        assert completion_event.wait(timeout=5.0), "异步处理超时"
        
        result = result_holder['result']
        assert result.success is True
        assert ProcessingStage.COMPLETED in result.stages_completed
        
        # 检查作业状态
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.processing_thread_id is not None
    
    def test_process_file_async_with_error(self):
        """测试异步处理中的错误处理"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 使用事件来同步测试
        completion_event = threading.Event()
        result_holder = {}
        
        def completion_callback(result):
            result_holder['result'] = result
            completion_event.set()
        
        # 创建一个会抛出异常的处理函数
        def failing_process_func(job):
            raise Exception("异步错误")
        
        # 直接使用ThreadManager提交失败的函数
        self.pipeline.thread_manager.submit_job(job, failing_process_func)
        
        # 等待处理完成（通过检查作业状态）
        for _ in range(50):  # 最多等待5秒
            updated_job = self.job_manager.get_job_status(job.id)
            if updated_job.status == JobStatus.FAILED:
                break
            time.sleep(0.1)
        
        # 检查作业状态
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert "线程处理错误" in updated_job.error_message
    
    def test_get_progress_callback(self):
        """测试进度回调函数"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        progress_callback = self.pipeline.get_progress_callback(job.id)
        
        # 调用进度回调
        progress_callback(ProcessingStage.TRANSCRIBING, 50.0)
        
        # 检查作业状态是否更新
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.current_stage == ProcessingStage.TRANSCRIBING
        assert updated_job.progress == 50.0
        assert updated_job.status == JobStatus.PROCESSING
    
    def test_handle_stage_error(self):
        """测试阶段错误处理"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        error = Exception("测试错误")
        
        self.pipeline.handle_stage_error(job, ProcessingStage.TRANSCRIBING, error)
        
        # 检查作业状态
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.current_stage == ProcessingStage.FAILED
        assert "阶段 transcribing 处理失败" in updated_job.error_message
    
    def test_cancel_job(self):
        """测试作业取消"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 启动异步处理
        self.pipeline.process_file_async(job)
        
        # 稍等一下让线程启动
        time.sleep(0.1)
        
        # 取消作业
        result = self.pipeline.cancel_job(job.id)
        assert result is True
        
        # 检查作业状态
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message == "作业已取消"
    
    def test_cancel_nonexistent_job(self):
        """测试取消不存在的作业"""
        result = self.pipeline.cancel_job("nonexistent_job")
        assert result is False
    
    def test_get_active_jobs_count(self):
        """测试获取活跃作业数量"""
        # 初始状态应该没有活跃作业
        assert self.pipeline.get_active_jobs_count() == 0
        
        # 创建并启动异步作业
        job1 = self.job_manager.create_job("/path/to/test1.mp4", "en")
        job2 = self.job_manager.create_job("/path/to/test2.mp4", "zh")
        
        # 使用较长的处理时间模拟
        with patch.object(self.pipeline, '_execute_stage') as mock_execute:
            mock_execute.side_effect = lambda job, stage: time.sleep(0.5)
            
            self.pipeline.process_file_async(job1)
            self.pipeline.process_file_async(job2)
            
            # 稍等一下让线程启动
            time.sleep(0.1)
            
            # 检查活跃作业数量
            assert self.pipeline.get_active_jobs_count() == 2
    
    def test_generate_output_path(self):
        """测试输出路径生成"""
        input_path = "/path/to/input/test.mp4"
        target_language = "en"
        
        output_path = self.pipeline._generate_output_path(input_path, target_language)
        
        assert "test_en_translated.mp4" in output_path
        assert "output" in output_path
    
    def test_execute_stage_coverage(self):
        """测试所有处理阶段的执行覆盖"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 测试所有处理阶段
        stages_to_test = [
            ProcessingStage.EXTRACTING_AUDIO,
            ProcessingStage.TRANSCRIBING,
            ProcessingStage.TRANSLATING,
            ProcessingStage.SYNTHESIZING,
            ProcessingStage.SYNCHRONIZING,
            ProcessingStage.FINALIZING
        ]
        
        for stage in stages_to_test:
            # 这应该不会抛出异常
            self.pipeline._execute_stage(job, stage)
    
    def test_shutdown(self):
        """测试管道关闭"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 启动异步处理
        with patch.object(self.pipeline, '_execute_stage') as mock_execute:
            mock_execute.side_effect = lambda job, stage: time.sleep(1.0)
            self.pipeline.process_file_async(job)
            
            # 稍等一下让线程启动
            time.sleep(0.1)
            
            # 关闭管道
            self.pipeline.shutdown()
            
            # 检查关闭标志
            assert self.pipeline._shutdown is True