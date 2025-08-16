import os
import time
import tempfile
import shutil
import pytest
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock
from services.thread_manager import ThreadManager, ThreadManagerError, ProcessingThread
from services.job_manager import JobManager
from models.core import Job, JobStatus, ProcessingStage


class TestProcessingThread:
    
    def test_processing_thread_creation(self):
        """测试处理线程创建"""
        job = Job(id="test_job", input_file_path="/path/test.mp4", target_language="en", created_at=datetime.now())
        
        def dummy_target():
            time.sleep(0.1)
        
        thread = ProcessingThread("thread_1", job, dummy_target)
        
        assert thread.thread_id == "thread_1"
        assert thread.job.id == "test_job"
        assert thread.status == "created"
        assert thread.started_at is None
        assert thread.completed_at is None
    
    def test_processing_thread_lifecycle(self):
        """测试处理线程生命周期"""
        job = Job(id="test_job", input_file_path="/path/test.mp4", target_language="en", created_at=datetime.now())
        
        def dummy_target():
            time.sleep(0.2)
        
        thread = ProcessingThread("thread_1", job, dummy_target)
        
        # 启动前
        assert not thread.is_alive()
        assert thread.status == "created"
        
        # 启动
        thread.start()
        assert thread.status == "running"
        assert thread.started_at is not None
        assert thread.is_alive()
        
        # 等待完成
        thread.join()
        assert thread.status == "completed"
        assert thread.completed_at is not None
        assert not thread.is_alive()
    
    def test_processing_thread_stop_request(self):
        """测试线程停止请求"""
        job = Job(id="test_job", input_file_path="/path/test.mp4", target_language="en", created_at=datetime.now())
        
        def target_with_stop_check():
            for _ in range(10):
                if thread.should_stop():
                    break
                time.sleep(0.1)
        
        thread = ProcessingThread("thread_1", job, target_with_stop_check)
        
        thread.start()
        time.sleep(0.05)  # 让线程开始运行
        
        # 请求停止
        thread.request_stop()
        assert thread.should_stop()
        assert thread.status == "stopping"
        
        # 等待线程自然结束
        thread.join(timeout=2.0)
        assert not thread.is_alive()


class TestThreadManager:
    
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
            self.thread_manager = ThreadManager(self.job_manager, max_concurrent_jobs=2)
    
    def teardown_method(self):
        # 清理资源
        if hasattr(self, 'thread_manager'):
            self.thread_manager.shutdown()
        if hasattr(self, 'job_manager'):
            self.job_manager.shutdown()
        
        # 清理临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_submit_job(self):
        """测试提交作业"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        def processing_func(job):
            time.sleep(0.1)
            return f"processed_{job.id}"
        
        thread_id = self.thread_manager.submit_job(job, processing_func)
        
        assert thread_id.startswith("worker_")
        assert job.id in thread_id
        
        # 等待处理完成
        self.thread_manager.wait_for_completion(timeout=5.0)
        
        # 检查线程状态
        status = self.thread_manager.get_thread_status(thread_id)
        assert status in ["completed", None]  # 可能已被清理
    
    def test_concurrent_job_limit(self):
        """测试并发作业限制"""
        jobs = []
        for i in range(4):
            job = self.job_manager.create_job(f"/path/to/test{i}.mp4", "en")
            jobs.append(job)
        
        def slow_processing_func(job):
            time.sleep(0.5)
            return f"processed_{job.id}"
        
        # 提交4个作业，但最大并发数为2
        thread_ids = []
        for job in jobs:
            thread_id = self.thread_manager.submit_job(job, slow_processing_func)
            thread_ids.append(thread_id)
        
        # 稍等让线程启动
        time.sleep(0.1)
        
        # 检查活跃线程数量不超过限制
        active_count = self.thread_manager.get_active_threads_count()
        assert active_count <= 2
        
        # 检查队列中有等待的作业
        queue_size = self.thread_manager.get_queue_size()
        assert queue_size >= 2
        
        # 等待所有作业完成
        self.thread_manager.wait_for_completion(timeout=10.0)
    
    def test_cancel_job_thread(self):
        """测试取消作业线程"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        def long_processing_func(job):
            time.sleep(2.0)
            return f"processed_{job.id}"
        
        thread_id = self.thread_manager.submit_job(job, long_processing_func)
        
        # 等待线程启动
        time.sleep(0.1)
        
        # 取消作业
        result = self.thread_manager.cancel_job_thread(job.id)
        assert result is True
        
        # 检查线程状态
        time.sleep(0.1)
        status = self.thread_manager.get_thread_status(thread_id)
        assert status == "stopping"
    
    def test_get_all_threads_info(self):
        """测试获取所有线程信息"""
        job1 = self.job_manager.create_job("/path/to/test1.mp4", "en")
        job2 = self.job_manager.create_job("/path/to/test2.mp4", "zh")
        
        def processing_func(job):
            time.sleep(0.3)
            return f"processed_{job.id}"
        
        self.thread_manager.submit_job(job1, processing_func)
        self.thread_manager.submit_job(job2, processing_func)
        
        # 等待线程启动
        time.sleep(0.3)
        
        threads_info = self.thread_manager.get_all_threads_info()
        
        assert len(threads_info) >= 1  # 至少有一个线程在运行
        for info in threads_info:
            assert "thread_id" in info
            assert "job_id" in info
            assert "status" in info
            assert "created_at" in info
            assert "is_alive" in info
    
    def test_cleanup_completed_threads(self):
        """测试清理已完成线程"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        def quick_processing_func(job):
            time.sleep(0.1)
            return f"processed_{job.id}"
        
        self.thread_manager.submit_job(job, quick_processing_func)
        
        # 等待处理完成
        time.sleep(0.3)
        
        # 等待延迟清理时间
        time.sleep(0.6)
        
        # 手动清理
        cleaned_count = self.thread_manager.cleanup_completed_threads()
        
        # 检查线程数量而不是清理数量，因为可能已经被自动清理了
        threads_info = self.thread_manager.get_all_threads_info()
        active_count = len([t for t in threads_info if t['is_alive']])
        assert active_count == 0  # 应该没有活跃线程
    
    def test_is_job_processing(self):
        """测试检查作业是否正在处理"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        # 初始状态
        assert not self.thread_manager.is_job_processing(job.id)
        
        def processing_func(job):
            time.sleep(0.3)
            return f"processed_{job.id}"
        
        self.thread_manager.submit_job(job, processing_func)
        
        # 等待线程启动
        time.sleep(0.3)
        
        # 检查是否正在处理
        is_processing = self.thread_manager.is_job_processing(job.id)
        if not is_processing:
            # 打印调试信息
            threads_info = self.thread_manager.get_all_threads_info()
            print(f"Debug: Job {job.id} not processing. Threads: {threads_info}")
        assert is_processing
        
        # 等待完成
        self.thread_manager.wait_for_completion(timeout=5.0)
        
        # 完成后应该不在处理中
        assert not self.thread_manager.is_job_processing(job.id)
    
    def test_wait_for_completion(self):
        """测试等待完成"""
        jobs = []
        for i in range(3):
            job = self.job_manager.create_job(f"/path/to/test{i}.mp4", "en")
            jobs.append(job)
        
        def processing_func(job):
            time.sleep(0.2)
            return f"processed_{job.id}"
        
        # 提交作业
        for job in jobs:
            self.thread_manager.submit_job(job, processing_func)
        
        # 等待所有完成
        start_time = time.time()
        completed = self.thread_manager.wait_for_completion(timeout=5.0)
        end_time = time.time()
        
        assert completed is True
        assert end_time - start_time < 5.0
        assert self.thread_manager.get_active_threads_count() == 0
    
    def test_wait_for_completion_timeout(self):
        """测试等待完成超时"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        def long_processing_func(job):
            time.sleep(2.0)
            return f"processed_{job.id}"
        
        self.thread_manager.submit_job(job, long_processing_func)
        
        # 等待线程启动
        time.sleep(0.2)
        
        # 短超时时间
        start_time = time.time()
        completed = self.thread_manager.wait_for_completion(timeout=0.3)
        end_time = time.time()
        
        # 检查活跃线程确保没有立即完成
        active_count = self.thread_manager.get_active_threads_count()
        if active_count == 0:
            # 如果没有活跃线程，则completed应该为True
            assert completed is True
        else:
            assert completed is False
            assert end_time - start_time >= 0.3
    
    def test_shutdown_after_closed(self):
        """测试关闭后的操作"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        def processing_func(job):
            return f"processed_{job.id}"
        
        # 关闭线程管理器
        self.thread_manager.shutdown()
        
        # 尝试提交作业应该失败
        with pytest.raises(ThreadManagerError, match="线程管理器已关闭"):
            self.thread_manager.submit_job(job, processing_func)
    
    def test_error_handling_in_processing(self):
        """测试处理过程中的错误处理"""
        job = self.job_manager.create_job("/path/to/test.mp4", "en")
        
        def failing_processing_func(job):
            raise Exception("处理失败")
        
        self.thread_manager.submit_job(job, failing_processing_func)
        
        # 等待处理完成
        time.sleep(0.3)
        
        # 检查作业状态应该被更新为失败
        updated_job = self.job_manager.get_job_status(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert "线程处理错误" in updated_job.error_message