import json
import os
import uuid
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
from models.core import Job, JobStatus, ProcessingStage
from config import Config


class JobManagerError(Exception):
    """作业管理器错误"""
    pass


class JobManager:
    """作业管理器：管理作业状态和进度跟踪，使用内存存储配合文件持久化"""
    
    def __init__(self):
        self.config = Config()
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._shutdown = False
        
        # 启动时加载已有作业状态
        self._load_jobs_from_file()
        
        # 启动后台线程定期保存状态
        self._save_thread = threading.Thread(target=self._periodic_save, daemon=True)
        self._save_thread.start()
    
    def create_job(self, file_path: str, target_language: str) -> Job:
        """创建新作业"""
        if target_language not in self.config.SUPPORTED_LANGUAGES:
            raise JobManagerError(f"不支持的目标语言: {target_language}")
        
        job_id = self._generate_job_id()
        now = datetime.now()
        
        job = Job(
            id=job_id,
            input_file_path=file_path,
            target_language=target_language,
            status=JobStatus.PENDING,
            progress=0.0,
            current_stage=ProcessingStage.UPLOADING,
            created_at=now
        )
        
        with self._lock:
            self._jobs[job_id] = job
        
        return job
    
    def update_progress(self, job_id: str, stage: ProcessingStage, progress: float) -> None:
        """更新作业进度"""
        with self._lock:
            if job_id not in self._jobs:
                raise JobManagerError(f"作业不存在: {job_id}")
            
            job = self._jobs[job_id]
            job.current_stage = stage
            job.progress = max(0.0, min(100.0, progress))
            
            # 根据阶段更新状态
            if stage == ProcessingStage.COMPLETED:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now()
            elif stage == ProcessingStage.FAILED:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now()
            elif job.status == JobStatus.PENDING:
                job.status = JobStatus.PROCESSING
    
    def get_job_status(self, job_id: str) -> Optional[Job]:
        """获取作业状态"""
        with self._lock:
            return self._jobs.get(job_id)
    
    def save_job_state(self, job: Job) -> None:
        """保存单个作业状态"""
        with self._lock:
            self._jobs[job.id] = job
    
    def load_job_state(self, job_id: str) -> Optional[Job]:
        """加载单个作业状态"""
        return self.get_job_status(job_id)
    
    def list_active_jobs(self) -> List[Job]:
        """列出活跃作业"""
        with self._lock:
            return [
                job for job in self._jobs.values()
                if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]
            ]
    
    def list_all_jobs(self) -> List[Job]:
        """列出所有作业"""
        with self._lock:
            return list(self._jobs.values())
    
    def update_job_thread_id(self, job_id: str, thread_id: str) -> None:
        """更新作业的处理线程ID"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].processing_thread_id = thread_id
    
    def update_job_output(self, job_id: str, output_path: str) -> None:
        """更新作业输出路径"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].output_file_path = output_path
    
    def update_job_error(self, job_id: str, error_message: str) -> None:
        """更新作业错误信息"""
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.error_message = error_message
                job.status = JobStatus.FAILED
                job.current_stage = ProcessingStage.FAILED
                job.completed_at = datetime.now()
    
    def _generate_job_id(self) -> str:
        """生成唯一作业标识符"""
        return f"job_{uuid.uuid4().hex[:12]}"
    
    def _load_jobs_from_file(self) -> None:
        """从文件加载作业状态"""
        if not os.path.exists(self.config.JOB_STATE_FILE):
            return
        
        try:
            with open(self.config.JOB_STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for job_data in data.get('jobs', []):
                # 解析日期时间字段
                if 'created_at' in job_data:
                    job_data['created_at'] = datetime.fromisoformat(job_data['created_at'])
                if 'completed_at' in job_data and job_data['completed_at']:
                    job_data['completed_at'] = datetime.fromisoformat(job_data['completed_at'])
                
                # 解析枚举字段
                job_data['status'] = JobStatus(job_data['status'])
                job_data['current_stage'] = ProcessingStage(job_data['current_stage'])
                
                job = Job(**job_data)
                self._jobs[job.id] = job
                
        except Exception as e:
            print(f"加载作业状态失败: {e}")
    
    def _save_jobs_to_file(self) -> None:
        """保存作业状态到文件"""
        try:
            jobs_data = []
            with self._lock:
                for job in self._jobs.values():
                    job_dict = job.model_dump()
                    # 序列化日期时间字段
                    if job_dict['created_at']:
                        job_dict['created_at'] = job_dict['created_at'].isoformat()
                    if job_dict['completed_at']:
                        job_dict['completed_at'] = job_dict['completed_at'].isoformat()
                    
                    # 序列化枚举字段
                    job_dict['status'] = job_dict['status'].value
                    job_dict['current_stage'] = job_dict['current_stage'].value
                    
                    jobs_data.append(job_dict)
            
            data = {'jobs': jobs_data}
            
            # 原子性写入
            temp_file = f"{self.config.JOB_STATE_FILE}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            os.rename(temp_file, self.config.JOB_STATE_FILE)
            
        except Exception as e:
            print(f"保存作业状态失败: {e}")
    
    def _periodic_save(self) -> None:
        """定期保存作业状态的后台线程"""
        while not self._shutdown:
            time.sleep(self.config.JOB_STATE_SAVE_INTERVAL)
            self._save_jobs_to_file()
    
    def shutdown(self) -> None:
        """关闭作业管理器"""
        self._shutdown = True
        # 最后保存一次状态
        self._save_jobs_to_file()
        if self._save_thread.is_alive():
            self._save_thread.join(timeout=5.0)