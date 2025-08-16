from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel


class FileType(Enum):
    VIDEO = "video"
    AUDIO = "audio"


class ProcessingStage(Enum):
    UPLOADING = "uploading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    SYNTHESIZING = "synthesizing"
    SYNCHRONIZING = "synchronizing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioProperties(BaseModel):
    sample_rate: int
    channels: int
    duration: float
    bitrate: Optional[int] = None


class VideoProperties(BaseModel):
    width: int
    height: int
    fps: float
    codec: str


class FileMetadata(BaseModel):
    file_type: FileType
    format: str
    duration: float
    size: int
    video_properties: Optional[VideoProperties] = None
    audio_properties: AudioProperties


class TimedSegment(BaseModel):
    start_time: float
    end_time: float
    original_text: str
    translated_text: str = ""
    confidence: Optional[float] = None
    speaker_id: Optional[str] = None


class Job(BaseModel):
    id: str
    input_file_path: str
    target_language: str
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    created_at: datetime
    completed_at: Optional[datetime] = None
    output_file_path: Optional[str] = None
    error_message: Optional[str] = None
    current_stage: ProcessingStage = ProcessingStage.UPLOADING
    processing_thread_id: Optional[str] = None


class ProcessingResult(BaseModel):
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    stages_completed: List[ProcessingStage] = []