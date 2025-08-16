import os
import json
import time
import tempfile
import shutil
import pytest
from datetime import datetime
from unittest.mock import patch
from services.job_manager import JobManager, JobManagerError
from models.core import Job, JobStatus, ProcessingStage


class TestJobManager:
    
    def setup_method(self):
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.job_state_file = os.path.join(self.temp_dir, "test_job_states.json")
        
        # 模拟配置
        with patch('services.job_manager.Config') as mock_config:
            config_instance = mock_config.return_value
            config_instance.SUPPORTED_LANGUAGES = ["en", "zh", "es", "fr", "de"]
            config_instance.JOB_STATE_FILE = self.job_state_file
            config_instance.JOB_STATE_SAVE_INTERVAL = 1  # 1秒用于测试
            
            self.job_manager = JobManager()
    
    def teardown_method(self):
        # 清理资源
        if hasattr(self, 'job_manager'):
            self.job_manager.shutdown()
        
        # 清理临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_job(self):
        """测试创建作业"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        assert job.id.startswith("job_")
        assert job.input_file_path == "/path/to/test.mp4"
        assert job.target_language == "en"
        assert job.status == JobStatus.PENDING
        assert job.progress == 0.0
        assert job.current_stage == ProcessingStage.UPLOADING
        assert job.created_at is not None
        assert job.completed_at is None
        assert job.output_file_path is None
        assert job.error_message is None
        assert job.processing_thread_id is None
    
    def test_create_job_unsupported_language(self):
        """测试创建作业时使用不支持的语言"""
        with pytest.raises(JobManagerError, match="不支持的目标语言"):
            self.job_manager.create_job("/path/to/test.mp4", "unsupported")
    
    def test_update_progress(self):
        """测试更新作业进度"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 更新进度
        self.job_manager.update_progress(job.id, ProcessingStage.TRANSCRIBING, 25.5)
        
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.current_stage == ProcessingStage.TRANSCRIBING
        assert updated_job.progress == 25.5
        assert updated_job.status == JobStatus.PROCESSING
    
    def test_update_progress_completed(self):
        """测试更新作业为完成状态"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 标记为完成
        self.job_manager.update_progress(job.id, ProcessingStage.COMPLETED, 100.0)
        
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.current_stage == ProcessingStage.COMPLETED
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.completed_at is not None
    
    def test_update_progress_failed(self):
        """测试更新作业为失败状态"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 标记为失败
        self.job_manager.update_progress(job.id, ProcessingStage.FAILED, 30.0)
        
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.current_stage == ProcessingStage.FAILED
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.completed_at is not None
    
    def test_update_progress_nonexistent_job(self):
        """测试更新不存在的作业进度"""
        with pytest.raises(JobManagerError, match="作业不存在"):
            self.job_manager.update_progress("nonexistent_job", ProcessingStage.TRANSCRIBING, 50.0)
    
    def test_get_job_status(self):
        """测试获取作业状态"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 获取存在的作业
        retrieved_job = self.job_manager.get_job_status(job.id)
        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        
        # 获取不存在的作业
        assert self.job_manager.get_job_status("nonexistent") is None
    
    def test_list_active_jobs(self):
        """测试列出活跃作业"""
        # 创建不同状态的作业
        job1 = self.job_manager.create_job("/path/to/test1.mp4", "en")
        job2 = self.job_manager.create_job("/path/to/test2.mp4", "zh")
        job3 = self.job_manager.create_job("/path/to/test3.mp4", "es")
        
        # 更新状态
        self.job_manager.update_progress(job2.id, ProcessingStage.TRANSCRIBING, 50.0)
        self.job_manager.update_progress(job3.id, ProcessingStage.COMPLETED, 100.0)
        
        # 获取活跃作业
        active_jobs = self.job_manager.list_active_jobs()
        active_job_ids = [job.id for job in active_jobs]
        
        assert len(active_jobs) == 2
        assert job1.id in active_job_ids
        assert job2.id in active_job_ids
        assert job3.id not in active_job_ids
    
    def test_update_job_thread_id(self):
        """测试更新作业线程ID"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        self.job_manager.update_job_thread_id(job.id, "thread_123")
        
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.processing_thread_id == "thread_123"
    
    def test_update_job_output(self):
        """测试更新作业输出路径"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        self.job_manager.update_job_output(job.id, "/path/to/output.mp4")
        
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.output_file_path == "/path/to/output.mp4"
    
    def test_update_job_error(self):
        """测试更新作业错误信息"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        self.job_manager.update_job_error(job.id, "API调用失败")
        
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.error_message == "API调用失败"
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.current_stage == ProcessingStage.FAILED
        assert updated_job.completed_at is not None
    
    def test_generate_job_id(self):
        """测试生成作业ID"""
        job_id = self.job_manager._generate_job_id()
        
        assert job_id.startswith("job_")
        assert len(job_id) == 16  # "job_" + 12字符的hex
        
        # 生成多个ID应该不同
        job_id2 = self.job_manager._generate_job_id()
        assert job_id != job_id2
    
    def test_save_and_load_jobs(self):
        """测试作业状态的保存和加载"""
        # 创建一些作业
        job1 = self.job_manager.create_job("/path/to/test1.mp4", "en")
        job2 = self.job_manager.create_job("/path/to/test2.mp4", "zh")
        
        # 更新状态
        self.job_manager.update_progress(job1.id, ProcessingStage.TRANSCRIBING, 50.0)
        self.job_manager.update_job_output(job2.id, "/path/to/output.mp4")
        
        # 手动保存
        self.job_manager._save_jobs_to_file()
        
        # 验证文件存在
        assert os.path.exists(self.job_state_file)
        
        # 创建新的管理器实例来测试加载
        with patch('services.job_manager.Config') as mock_config:
            config_instance = mock_config.return_value
            config_instance.SUPPORTED_LANGUAGES = ["en", "zh", "es", "fr", "de"]
            config_instance.JOB_STATE_FILE = self.job_state_file
            config_instance.JOB_STATE_SAVE_INTERVAL = 1
            
            new_manager = JobManager()
        
        try:
            # 验证作业被正确加载
            loaded_job1 = new_manager.get_job_status(job1.id)
            loaded_job2 = new_manager.get_job_status(job2.id)
            
            assert loaded_job1 is not None
            assert loaded_job1.current_stage == ProcessingStage.TRANSCRIBING
            assert loaded_job1.progress == 50.0
            
            assert loaded_job2 is not None
            assert loaded_job2.output_file_path == "/path/to/output.mp4"
        finally:
            new_manager.shutdown()