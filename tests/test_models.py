import pytest
from datetime import datetime
from models.core import (
    FileType, ProcessingStage, JobStatus,
    AudioProperties, VideoProperties, FileMetadata,
    TimedSegment, Job, ProcessingResult
)


def test_file_type_enum():
    assert FileType.VIDEO.value == "video"
    assert FileType.AUDIO.value == "audio"


def test_processing_stage_enum():
    assert ProcessingStage.UPLOADING.value == "uploading"
    assert ProcessingStage.COMPLETED.value == "completed"


def test_job_status_enum():
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.COMPLETED.value == "completed"


def test_audio_properties():
    audio_props = AudioProperties(
        sample_rate=48000,
        channels=2,
        duration=120.5,
        bitrate=128000
    )
    assert audio_props.sample_rate == 48000
    assert audio_props.channels == 2
    assert audio_props.duration == 120.5
    assert audio_props.bitrate == 128000


def test_video_properties():
    video_props = VideoProperties(
        width=1920,
        height=1080,
        fps=30.0,
        codec="h264"
    )
    assert video_props.width == 1920
    assert video_props.height == 1080
    assert video_props.fps == 30.0
    assert video_props.codec == "h264"


def test_file_metadata():
    audio_props = AudioProperties(
        sample_rate=48000,
        channels=2,
        duration=120.5
    )
    
    metadata = FileMetadata(
        file_type=FileType.AUDIO,
        format="mp3",
        duration=120.5,
        size=5242880,
        audio_properties=audio_props
    )
    
    assert metadata.file_type == FileType.AUDIO
    assert metadata.format == "mp3"
    assert metadata.duration == 120.5
    assert metadata.size == 5242880
    assert metadata.video_properties is None
    assert metadata.audio_properties.sample_rate == 48000


def test_timed_segment():
    segment = TimedSegment(
        start_time=0.0,
        end_time=2.5,
        original_text="Hello world",
        translated_text="你好世界",
        confidence=0.95,
        speaker_id="speaker_1"
    )
    
    assert segment.start_time == 0.0
    assert segment.end_time == 2.5
    assert segment.original_text == "Hello world"
    assert segment.translated_text == "你好世界"
    assert segment.confidence == 0.95
    assert segment.speaker_id == "speaker_1"


def test_job():
    now = datetime.now()
    job = Job(
        id="job_123",
        input_file_path="/path/to/input.mp4",
        target_language="zh",
        created_at=now
    )
    
    assert job.id == "job_123"
    assert job.input_file_path == "/path/to/input.mp4"
    assert job.target_language == "zh"
    assert job.status == JobStatus.PENDING
    assert job.progress == 0.0
    assert job.created_at == now
    assert job.completed_at is None
    assert job.output_file_path is None
    assert job.error_message is None
    assert job.current_stage == ProcessingStage.UPLOADING


def test_job_with_optional_fields():
    now = datetime.now()
    completed_time = datetime.now()
    
    job = Job(
        id="job_456",
        input_file_path="/path/to/input.mp3",
        target_language="en",
        status=JobStatus.COMPLETED,
        progress=100.0,
        created_at=now,
        completed_at=completed_time,
        output_file_path="/path/to/output.mp3",
        current_stage=ProcessingStage.COMPLETED,
        processing_thread_id="thread_123"
    )
    
    assert job.status == JobStatus.COMPLETED
    assert job.progress == 100.0
    assert job.completed_at == completed_time
    assert job.output_file_path == "/path/to/output.mp3"
    assert job.current_stage == ProcessingStage.COMPLETED
    assert job.processing_thread_id == "thread_123"


def test_processing_result():
    result = ProcessingResult(
        success=True,
        output_path="/path/to/output.mp4",
        processing_time=45.5,
        stages_completed=[
            ProcessingStage.EXTRACTING_AUDIO,
            ProcessingStage.TRANSCRIBING,
            ProcessingStage.TRANSLATING
        ]
    )
    
    assert result.success is True
    assert result.output_path == "/path/to/output.mp4"
    assert result.error_message is None
    assert result.processing_time == 45.5
    assert len(result.stages_completed) == 3
    assert ProcessingStage.EXTRACTING_AUDIO in result.stages_completed


def test_processing_result_failure():
    result = ProcessingResult(
        success=False,
        error_message="翻译服务API调用失败",
        processing_time=12.3,
        stages_completed=[ProcessingStage.EXTRACTING_AUDIO]
    )
    
    assert result.success is False
    assert result.output_path is None
    assert result.error_message == "翻译服务API调用失败"
    assert result.processing_time == 12.3
    assert len(result.stages_completed) == 1


def test_job_with_new_fields():
    now = datetime.now()
    job = Job(
        id="job_789",
        input_file_path="/path/to/test.mp4",
        target_language="fr",
        created_at=now,
        current_stage=ProcessingStage.TRANSCRIBING,
        processing_thread_id="worker_thread_1"
    )
    
    assert job.id == "job_789"
    assert job.current_stage == ProcessingStage.TRANSCRIBING
    assert job.processing_thread_id == "worker_thread_1"
    assert job.status == JobStatus.PENDING  # 默认值
    assert job.progress == 0.0  # 默认值