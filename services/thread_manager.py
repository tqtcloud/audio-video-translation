import threading
import time
import queue
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from models.core import Job, JobStatus, ProcessingStage
from services.job_manager import JobManager


class ThreadManagerError(Exception):
    """线程管理器错误"""
    pass


class ProcessingThread:
    """处理线程包装器"""
    
    def __init__(self, thread_id: str, job: Job, target: Callable, args: tuple = (), kwargs: dict = None):
        self.thread_id = thread_id
        self.job = job
        self.thread = threading.Thread(target=target, args=args, kwargs=kwargs or {}, daemon=True)
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.status = "created"
        self._stop_event = threading.Event()
    
    def start(self):
        """启动线程"""
        self.thread.start()
        self.started_at = datetime.now()
        self.status = "running"
    
    def is_alive(self) -> bool:
        """检查线程是否活跃"""
        return self.thread.is_alive()
    
    def join(self, timeout: Optional[float] = None) -> None:
        """等待线程完成"""
        self.thread.join(timeout)
        if not self.thread.is_alive():
            self.completed_at = datetime.now()
            self.status = "completed"
    
    def request_stop(self):
        """请求停止线程"""
        self._stop_event.set()
        self.status = "stopping"
    
    def should_stop(self) -> bool:
        """检查是否应该停止"""
        return self._stop_event.is_set()


class ThreadManager:
    """
    线程管理器
    
    负责管理处理线程的生命周期，提供线程安全的状态更新机制，
    支持并发处理和资源管理。
    """
    
    def __init__(self, job_manager: JobManager, max_concurrent_jobs: int = 5):
        self.job_manager = job_manager
        self.max_concurrent_jobs = max_concurrent_jobs
        
        # 线程管理
        self._threads: Dict[str, ProcessingThread] = {}
        self._lock = threading.Lock()
        self._shutdown = False
        
        # 作业队列
        self._job_queue = queue.Queue()
        self._processing_jobs = set()
        
        # 启动线程池管理器
        self._manager_thread = threading.Thread(target=self._thread_manager_loop, daemon=True)
        self._manager_thread.start()
    
    def submit_job(self, job: Job, processing_func: Callable[[Job], Any]) -> str:
        """
        提交作业进行处理
        
        Args:
            job: 要处理的作业
            processing_func: 处理函数
            
        Returns:
            线程ID
        """
        if self._shutdown:
            raise ThreadManagerError("线程管理器已关闭")
        
        thread_id = f"worker_{job.id}_{int(time.time())}"
        
        # 将作业添加到队列
        self._job_queue.put((job, processing_func, thread_id))
        
        return thread_id
    
    def get_thread_status(self, thread_id: str) -> Optional[str]:
        """
        获取线程状态
        
        Args:
            thread_id: 线程ID
            
        Returns:
            线程状态
        """
        with self._lock:
            if thread_id in self._threads:
                return self._threads[thread_id].status
        return None
    
    def get_active_threads_count(self) -> int:
        """获取活跃线程数量"""
        with self._lock:
            return len([t for t in self._threads.values() if t.is_alive()])
    
    def get_all_threads_info(self) -> List[Dict[str, Any]]:
        """获取所有线程信息"""
        with self._lock:
            info = []
            for thread_id, processing_thread in self._threads.items():
                info.append({
                    "thread_id": thread_id,
                    "job_id": processing_thread.job.id,
                    "status": processing_thread.status,
                    "created_at": processing_thread.created_at,
                    "started_at": processing_thread.started_at,
                    "completed_at": processing_thread.completed_at,
                    "is_alive": processing_thread.is_alive()
                })
            return info
    
    def cancel_job_thread(self, job_id: str) -> bool:
        """
        取消作业的处理线程
        
        Args:
            job_id: 作业ID
            
        Returns:
            是否成功取消
        """
        with self._lock:
            for thread_id, processing_thread in self._threads.items():
                if processing_thread.job.id == job_id and processing_thread.is_alive():
                    processing_thread.request_stop()
                    return True
        return False
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        等待所有线程完成
        
        Args:
            timeout: 超时时间
            
        Returns:
            是否所有线程都完成
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                active_threads = [t for t in self._threads.values() if t.is_alive()]
            
            if not active_threads:
                return True
            
            if timeout and (time.time() - start_time) > timeout:
                return False
            
            time.sleep(0.1)
    
    def cleanup_completed_threads(self) -> int:
        """
        清理已完成的线程
        
        Returns:
            清理的线程数量
        """
        with self._lock:
            completed_thread_ids = []
            for thread_id, processing_thread in self._threads.items():
                if not processing_thread.is_alive():
                    if processing_thread.status != "stopping":
                        processing_thread.status = "completed"
                        processing_thread.completed_at = datetime.now()
                    completed_thread_ids.append(thread_id)
            
            # 延迟清理，给测试一些时间检查状态
            current_time = datetime.now()
            for thread_id in list(completed_thread_ids):
                processing_thread = self._threads[thread_id]
                if processing_thread.completed_at and (current_time - processing_thread.completed_at).total_seconds() > 0.5:
                    del self._threads[thread_id]
                    if thread_id in self._processing_jobs:
                        self._processing_jobs.remove(thread_id)
                else:
                    completed_thread_ids.remove(thread_id)
            
            return len(completed_thread_ids)
    
    def shutdown(self, timeout: float = 10.0) -> None:
        """
        关闭线程管理器
        
        Args:
            timeout: 等待线程完成的超时时间
        """
        self._shutdown = True
        
        # 请求所有线程停止
        with self._lock:
            for processing_thread in self._threads.values():
                if processing_thread.is_alive():
                    processing_thread.request_stop()
        
        # 等待所有线程完成
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                active_threads = [t for t in self._threads.values() if t.is_alive()]
            
            if not active_threads:
                break
            
            time.sleep(0.1)
        
        # 强制等待管理线程结束
        if self._manager_thread.is_alive():
            self._manager_thread.join(timeout=5.0)
    
    def _thread_manager_loop(self) -> None:
        """线程管理器主循环"""
        while not self._shutdown:
            try:
                # 清理已完成的线程
                self.cleanup_completed_threads()
                
                # 检查是否可以启动新的作业
                current_active = self.get_active_threads_count()
                
                if current_active < self.max_concurrent_jobs:
                    try:
                        # 从队列中获取作业（非阻塞）
                        job, processing_func, thread_id = self._job_queue.get_nowait()
                        
                        # 创建并启动处理线程
                        self._start_processing_thread(job, processing_func, thread_id)
                        
                    except queue.Empty:
                        pass
                
                time.sleep(0.01)  # 减少延迟以提高响应性
                
            except Exception as e:
                print(f"线程管理器循环错误: {e}")
                time.sleep(1.0)
    
    def _start_processing_thread(self, job: Job, processing_func: Callable, thread_id: str) -> None:
        """启动处理线程"""
        def _wrapped_processing():
            try:
                # 更新作业的线程ID
                self.job_manager.update_job_thread_id(job.id, thread_id)
                
                # 添加到处理中集合
                with self._lock:
                    self._processing_jobs.add(thread_id)
                
                # 执行处理函数
                result = processing_func(job)
                
                return result
                
            except Exception as e:
                # 处理异常
                error_message = f"线程处理错误: {str(e)}"
                self.job_manager.update_job_error(job.id, error_message)
                print(f"线程 {thread_id} 处理失败: {error_message}")
                
            finally:
                # 从处理中集合移除
                with self._lock:
                    if thread_id in self._processing_jobs:
                        self._processing_jobs.remove(thread_id)
        
        # 创建处理线程
        processing_thread = ProcessingThread(
            thread_id=thread_id,
            job=job,
            target=_wrapped_processing
        )
        
        # 添加到线程字典
        with self._lock:
            self._threads[thread_id] = processing_thread
        
        # 启动线程
        processing_thread.start()
        
        print(f"启动处理线程 {thread_id} 为作业 {job.id}")
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self._job_queue.qsize()
    
    def is_job_processing(self, job_id: str) -> bool:
        """检查作业是否正在处理中"""
        with self._lock:
            for processing_thread in self._threads.values():
                if (processing_thread.job.id == job_id and 
                    processing_thread.is_alive()):
                    return True
        return False