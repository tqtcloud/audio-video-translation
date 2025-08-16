import pytest
import tempfile
import os
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from services.integrated_pipeline import IntegratedPipeline, PipelineConfig, PipelineResult, IntegratedPipelineError
from services.output_generator import OutputConfig
from models.core import Job, ProcessingStage, FileMetadata, FileType, TimedSegment


class TestIntegratedPipeline:
    
    def setup_method(self):
        # 创建测试配置
        self.config = PipelineConfig(
            target_language="zh-CN",
            voice_model="alloy",
            preserve_background_audio=True,
            enable_fault_tolerance=False,  # 禁用容错以简化测试
            output_config=OutputConfig(
                output_directory="./test_output",
                file_naming_pattern="{name}_translated"
            )
        )
        
        # 模拟所有服务组件
        self._mock_all_services()
        
        # 创建管道实例
        self.pipeline = IntegratedPipeline(self.config)
    
    def _mock_all_services(self):
        """模拟所有服务组件"""
        # 模拟文件验证器
        self.mock_file_validator = Mock()
        self.mock_file_validator.validate_file.return_value = Mock(is_valid=True)
        self.mock_file_validator.extract_metadata.return_value = FileMetadata(
            file_path="/test/file.mp4",
            file_type=FileType.VIDEO,
            file_size=1000000,
            duration=60.0
        )
        
        # 模拟音频提取器
        self.mock_audio_extractor = Mock()
        self.mock_audio_extractor.extract_audio.return_value = "/test/extracted_audio.wav"
        self.mock_audio_extractor.get_audio_properties.return_value = {
            "sample_rate": 44100,
            "channels": 2,
            "duration": 60.0
        }
        
        # 模拟语音转文本服务
        self.mock_speech_to_text = Mock()
        mock_segments = [
            TimedSegment(start_time=0.0, end_time=5.0, original_text="Hello world", translated_text="", confidence=-0.1),
            TimedSegment(start_time=5.0, end_time=10.0, original_text="How are you", translated_text="", confidence=-0.2)
        ]
        self.mock_speech_to_text.transcribe_audio.return_value = Mock(
            transcript="Hello world. How are you?",
            segments=mock_segments,
            language="en",
            confidence=0.95
        )
        
        # 模拟翻译服务
        self.mock_translation_service = Mock()
        translated_segments = [
            TimedSegment(start_time=0.0, end_time=5.0, original_text="Hello world", translated_text="你好世界", confidence=-0.1),
            TimedSegment(start_time=5.0, end_time=10.0, original_text="How are you", translated_text="你好吗", confidence=-0.2)
        ]
        self.mock_translation_service.translate_segments.return_value = translated_segments
        
        # 模拟文本转语音服务
        self.mock_text_to_speech = Mock()
        self.mock_text_to_speech.synthesize_segments.return_value = Mock(
            audio_file_path="/test/synthesized.wav",
            quality_score=0.9,
            total_duration=10.0
        )
        
        # 模拟音频同步器
        self.mock_audio_synchronizer = Mock()
        self.mock_audio_synchronizer.analyze_sync_quality.return_value = Mock(
            sync_quality_score=0.85,
            timing_accuracy=0.9
        )
        self.mock_audio_synchronizer.adjust_audio_timing.return_value = Mock(
            adjusted_audio_path="/test/adjusted.wav"
        )
        
        # 模拟音频优化器
        self.mock_audio_optimizer = Mock()
        self.mock_audio_optimizer.optimize_audio_timing.return_value = Mock(
            optimized_audio_path="/test/optimized.wav"
        )
        
        # 模拟视频组装器
        self.mock_video_assembler = Mock()
        self.mock_video_assembler.replace_audio_track.return_value = Mock(
            output_video_path="/test/output.mp4",
            quality_preserved=True
        )
        
        # 模拟输出生成器
        self.mock_output_generator = Mock()
        self.mock_output_generator.generate_video_output.return_value = Mock(
            output_path="/test/final_output.mp4"
        )
        self.mock_output_generator.generate_audio_output.return_value = Mock(
            output_path="/test/final_output.mp3"
        )
    
    @patch('services.integrated_pipeline.FileValidator')
    @patch('services.integrated_pipeline.AudioExtractor')
    @patch('services.integrated_pipeline.SpeechToTextService')
    @patch('services.integrated_pipeline.TranslationService')
    @patch('services.integrated_pipeline.TextToSpeechService')
    @patch('services.integrated_pipeline.AudioSynchronizer')
    @patch('services.integrated_pipeline.AudioOptimizer')
    @patch('services.integrated_pipeline.VideoAssembler')
    @patch('services.integrated_pipeline.OutputGenerator')
    def test_initialization_success(self, mock_output_gen, mock_video_asm, mock_audio_opt,
                                  mock_audio_sync, mock_tts, mock_translation, 
                                  mock_stt, mock_audio_ext, mock_file_val):
        """测试成功的初始化"""
        # 设置模拟对象
        mock_file_val.return_value = self.mock_file_validator
        mock_audio_ext.return_value = self.mock_audio_extractor
        mock_stt.return_value = self.mock_speech_to_text
        mock_translation.return_value = self.mock_translation_service
        mock_tts.return_value = self.mock_text_to_speech
        mock_audio_sync.return_value = self.mock_audio_synchronizer
        mock_audio_opt.return_value = self.mock_audio_optimizer
        mock_video_asm.return_value = self.mock_video_assembler
        mock_output_gen.return_value = self.mock_output_generator
        
        pipeline = IntegratedPipeline(self.config)
        
        assert pipeline.config.target_language == "zh-CN"
        assert pipeline.config.voice_model == "alloy"
        assert pipeline.job_manager is not None
        assert pipeline.error_handler is not None
        assert pipeline.pipeline is not None
    
    @patch('services.integrated_pipeline.FileValidator')
    def test_initialization_failure(self, mock_file_val):
        """测试初始化失败"""
        mock_file_val.side_effect = Exception("初始化失败")
        
        with pytest.raises(IntegratedPipelineError, match="服务初始化失败"):
            IntegratedPipeline(self.config)
    
    def test_process_file_creates_job(self):
        """测试处理文件创建作业"""
        with patch.object(self.pipeline, '_process_job_async'):
            job_id = self.pipeline.process_file("/test/input.mp4")
            
            assert job_id is not None
            job = self.pipeline.job_manager.get_job(job_id)
            assert job is not None
            assert job.file_path == "/test/input.mp4"
            assert job.target_language == "zh-CN"
    
    def test_process_file_with_custom_language(self):
        """测试使用自定义语言处理文件"""
        with patch.object(self.pipeline, '_process_job_async'):
            job_id = self.pipeline.process_file("/test/input.mp4", "es")
            
            job = self.pipeline.job_manager.get_job(job_id)
            assert job.target_language == "es"
    
    @patch('services.integrated_pipeline.threading.Thread')
    def test_process_file_starts_thread(self, mock_thread):
        """测试处理文件启动线程"""
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        job_id = self.pipeline.process_file("/test/input.mp4")
        
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
    
    def test_get_processing_result_success(self):
        """测试获取成功的处理结果"""
        # 创建一个完成的作业
        job = Job(
            file_path="/test/input.mp4",
            target_language="zh-CN",
            created_at=time.time()
        )
        job.current_stage = ProcessingStage.COMPLETED
        job.processing_time = 120.0
        job.output_file_path = "/test/output.mp4"
        
        job_id = self.pipeline.job_manager.create_job(job)
        
        result = self.pipeline.get_processing_result(job_id)
        
        assert isinstance(result, PipelineResult)
        assert result.job_id == job_id
        assert result.success is True
        assert result.processing_time == 120.0
        assert result.output_file_path == "/test/output.mp4"
        assert len(result.stages_completed) > 0
    
    def test_get_processing_result_failure(self):
        """测试获取失败的处理结果"""
        # 创建一个失败的作业
        job = Job(
            file_path="/test/input.mp4",
            target_language="zh-CN",
            created_at=time.time()
        )
        job.current_stage = ProcessingStage.FAILED
        job.error_message = "处理失败"
        
        job_id = self.pipeline.job_manager.create_job(job)
        
        result = self.pipeline.get_processing_result(job_id)
        
        assert result.success is False
        assert result.error_message == "处理失败"
    
    def test_get_processing_result_nonexistent_job(self):
        """测试获取不存在作业的结果"""
        with pytest.raises(IntegratedPipelineError, match="作业不存在"):
            self.pipeline.get_processing_result("nonexistent_job_id")
    
    def test_file_validation_stage(self):
        """测试文件验证阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        
        # 设置模拟服务
        self.pipeline.file_validator = self.mock_file_validator
        
        result = self.pipeline._execute_file_validation(job)
        
        assert "validation_result" in result
        assert "metadata" in result
        self.mock_file_validator.validate_file.assert_called_once_with("/test/input.mp4")
        self.mock_file_validator.extract_metadata.assert_called_once_with("/test/input.mp4")
    
    def test_audio_extraction_stage_video(self):
        """测试视频文件的音频提取阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        job.metadata = FileMetadata(
            file_path="/test/input.mp4",
            file_type=FileType.VIDEO,
            file_size=1000000
        )
        
        # 设置模拟服务
        self.pipeline.audio_extractor = self.mock_audio_extractor
        
        result = self.pipeline._execute_audio_extraction(job)
        
        assert "audio_path" in result
        assert "audio_properties" in result
        self.mock_audio_extractor.extract_audio.assert_called_once_with("/test/input.mp4")
    
    def test_audio_extraction_stage_audio(self):
        """测试音频文件的音频提取阶段"""
        job = Job(file_path="/test/input.mp3", target_language="zh-CN", created_at=time.time())
        job.metadata = FileMetadata(
            file_path="/test/input.mp3",
            file_type=FileType.AUDIO,
            file_size=1000000
        )
        
        result = self.pipeline._execute_audio_extraction(job)
        
        assert result["audio_path"] == "/test/input.mp3"
        # 音频文件不需要提取
        self.mock_audio_extractor.extract_audio.assert_not_called()
    
    def test_speech_to_text_stage(self):
        """测试语音转文本阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        job.intermediate_results = {
            "audio_extraction": {"audio_path": "/test/audio.wav"}
        }
        
        # 设置模拟服务
        self.pipeline.speech_to_text = self.mock_speech_to_text
        
        result = self.pipeline._execute_speech_to_text(job)
        
        assert "transcription" in result
        assert "segments" in result
        assert "language" in result
        assert "confidence" in result
        self.mock_speech_to_text.transcribe_audio.assert_called_once_with("/test/audio.wav")
    
    def test_text_translation_stage(self):
        """测试文本翻译阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        mock_segments = [
            TimedSegment(start_time=0.0, end_time=5.0, original_text="Hello", translated_text="", confidence=-0.1)
        ]
        job.intermediate_results = {
            "speech_to_text": {
                "segments": mock_segments,
                "language": "en"
            }
        }
        
        # 设置模拟服务
        self.pipeline.translation_service = self.mock_translation_service
        
        result = self.pipeline._execute_text_translation(job)
        
        assert "translated_segments" in result
        assert "source_language" in result
        assert "target_language" in result
        self.mock_translation_service.translate_segments.assert_called_once_with(
            mock_segments, "en", "zh-CN"
        )
    
    def test_text_to_speech_stage(self):
        """测试文本转语音阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        mock_translated_segments = [
            TimedSegment(start_time=0.0, end_time=5.0, original_text="Hello", translated_text="你好", confidence=-0.1)
        ]
        job.intermediate_results = {
            "text_translation": {"translated_segments": mock_translated_segments}
        }
        
        # 设置模拟服务
        self.pipeline.text_to_speech = self.mock_text_to_speech
        
        result = self.pipeline._execute_text_to_speech(job)
        
        assert "synthesized_audio_path" in result
        assert "synthesis_quality" in result
        assert "total_duration" in result
        self.mock_text_to_speech.synthesize_segments.assert_called_once_with(
            mock_translated_segments, voice="alloy", target_language="zh-CN"
        )
    
    def test_audio_sync_stage(self):
        """测试音频同步阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        mock_segments = [
            TimedSegment(start_time=0.0, end_time=5.0, original_text="Hello", translated_text="", confidence=-0.1)
        ]
        job.intermediate_results = {
            "speech_to_text": {"segments": mock_segments},
            "text_to_speech": {"synthesized_audio_path": "/test/synthesized.wav"}
        }
        
        # 设置模拟服务
        self.pipeline.audio_synchronizer = self.mock_audio_synchronizer
        self.pipeline.audio_optimizer = self.mock_audio_optimizer
        
        result = self.pipeline._execute_audio_sync(job)
        
        assert "final_audio_path" in result
        assert "sync_analysis" in result
        assert "optimization_result" in result
        self.mock_audio_synchronizer.analyze_sync_quality.assert_called_once()
        self.mock_audio_optimizer.optimize_audio_timing.assert_called_once()
    
    def test_video_assembly_stage_video(self):
        """测试视频文件的视频组装阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        job.metadata = FileMetadata(
            file_path="/test/input.mp4",
            file_type=FileType.VIDEO,
            file_size=1000000
        )
        job.intermediate_results = {
            "audio_sync": {"final_audio_path": "/test/final_audio.wav"}
        }
        
        # 设置模拟服务
        self.pipeline.video_assembler = self.mock_video_assembler
        
        result = self.pipeline._execute_video_assembly(job)
        
        assert "output_video_path" in result
        assert "quality_preserved" in result
        self.mock_video_assembler.replace_audio_track.assert_called_once_with(
            "/test/input.mp4", "/test/final_audio.wav", preserve_quality=True
        )
    
    def test_video_assembly_stage_audio(self):
        """测试音频文件的视频组装阶段"""
        job = Job(file_path="/test/input.mp3", target_language="zh-CN", created_at=time.time())
        job.metadata = FileMetadata(
            file_path="/test/input.mp3",
            file_type=FileType.AUDIO,
            file_size=1000000
        )
        job.intermediate_results = {
            "audio_sync": {"final_audio_path": "/test/final_audio.wav"}
        }
        
        result = self.pipeline._execute_video_assembly(job)
        
        assert "output_audio_path" in result
        assert result["output_audio_path"] == "/test/final_audio.wav"
        # 音频文件不需要视频组装
        self.mock_video_assembler.replace_audio_track.assert_not_called()
    
    def test_output_generation_stage_video(self):
        """测试视频的输出生成阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        job.intermediate_results = {
            "video_assembly": {"output_video_path": "/test/assembled.mp4"},
            "audio_sync": {"final_audio_path": "/test/final_audio.wav"}
        }
        
        # 设置模拟服务
        self.pipeline.output_generator = self.mock_output_generator
        
        result = self.pipeline._execute_output_generation(job)
        
        assert "output_result" in result
        assert "final_output_path" in result
        assert job.output_file_path is not None
        self.mock_output_generator.generate_video_output.assert_called_once()
    
    def test_output_generation_stage_audio(self):
        """测试音频的输出生成阶段"""
        job = Job(file_path="/test/input.mp3", target_language="zh-CN", created_at=time.time())
        job.intermediate_results = {
            "video_assembly": {"output_audio_path": "/test/final_audio.wav"},
            "audio_sync": {"final_audio_path": "/test/final_audio.wav"}
        }
        
        # 设置模拟服务
        self.pipeline.output_generator = self.mock_output_generator
        
        result = self.pipeline._execute_output_generation(job)
        
        assert "output_result" in result
        assert "final_output_path" in result
        self.mock_output_generator.generate_audio_output.assert_called_once()
    
    def test_get_job_status(self):
        """测试获取作业状态"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        job_id = self.pipeline.job_manager.create_job(job)
        
        status = self.pipeline.get_job_status(job_id)
        
        assert status is not None
        assert status.file_path == "/test/input.mp4"
    
    def test_get_job_status_nonexistent(self):
        """测试获取不存在作业的状态"""
        status = self.pipeline.get_job_status("nonexistent_job_id")
        assert status is None
    
    def test_list_active_jobs(self):
        """测试列出活跃作业"""
        # 模拟一些活跃作业
        self.pipeline._active_jobs = {
            "job1": Mock(),
            "job2": Mock()
        }
        
        active_jobs = self.pipeline.list_active_jobs()
        
        assert len(active_jobs) == 2
        assert "job1" in active_jobs
        assert "job2" in active_jobs
    
    def test_cancel_job_existing(self):
        """测试取消存在的作业"""
        # 模拟活跃作业
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        job_id = self.pipeline.job_manager.create_job(job)
        self.pipeline._active_jobs[job_id] = Mock()
        
        result = self.pipeline.cancel_job(job_id)
        
        assert result is True
        # 检查作业状态是否更新为失败
        updated_job = self.pipeline.job_manager.get_job(job_id)
        assert updated_job.current_stage == ProcessingStage.FAILED
    
    def test_cancel_job_nonexistent(self):
        """测试取消不存在的作业"""
        result = self.pipeline.cancel_job("nonexistent_job_id")
        assert result is False
    
    def test_get_system_metrics(self):
        """测试获取系统指标"""
        # 模拟一些活跃作业
        self.pipeline._active_jobs = {"job1": Mock()}
        
        metrics = self.pipeline.get_system_metrics()
        
        assert "active_jobs_count" in metrics
        assert "total_jobs_processed" in metrics
        assert "fault_tolerance_metrics" in metrics
        assert "error_statistics" in metrics
        assert metrics["active_jobs_count"] == 1
    
    def test_progress_callback(self):
        """测试进度回调"""
        callback_calls = []
        
        def test_callback(job_id, progress, message):
            callback_calls.append((job_id, progress, message))
        
        config = PipelineConfig(progress_callback=test_callback)
        pipeline = IntegratedPipeline(config)
        
        # 触发进度回调
        pipeline._internal_progress_callback("test_job", 0.5, "Processing...")
        
        assert len(callback_calls) == 1
        assert callback_calls[0] == ("test_job", 0.5, "Processing...")
    
    def test_get_completed_stages(self):
        """测试获取已完成阶段"""
        job = Job(file_path="/test/input.mp4", target_language="zh-CN", created_at=time.time())
        job.current_stage = ProcessingStage.SPEECH_TO_TEXT
        
        completed_stages = self.pipeline._get_completed_stages(job)
        
        expected_stages = [
            ProcessingStage.FILE_VALIDATION,
            ProcessingStage.AUDIO_EXTRACTION,
            ProcessingStage.SPEECH_TO_TEXT
        ]
        
        assert len(completed_stages) == 3
        for stage in expected_stages:
            assert stage in completed_stages
    
    def test_shutdown(self):
        """测试关闭管道"""
        # 模拟一些活跃线程
        mock_thread = Mock()
        self.pipeline._active_jobs = {"job1": mock_thread}
        
        self.pipeline.shutdown()
        
        # 验证线程被等待
        mock_thread.join.assert_called_once_with(timeout=30)
        
        # 验证活跃作业被清理
        assert len(self.pipeline._active_jobs) == 0


class TestPipelineConfig:
    
    def test_default_config(self):
        """测试默认配置"""
        config = PipelineConfig()
        
        assert config.target_language == "zh-CN"
        assert config.voice_model == "alloy"
        assert config.preserve_background_audio is True
        assert config.enable_fault_tolerance is True
        assert config.max_retries == 3
        assert config.progress_callback is None
    
    def test_custom_config(self):
        """测试自定义配置"""
        def dummy_callback(job_id, progress, message):
            pass
        
        config = PipelineConfig(
            target_language="es",
            voice_model="nova",
            preserve_background_audio=False,
            enable_fault_tolerance=False,
            max_retries=5,
            progress_callback=dummy_callback
        )
        
        assert config.target_language == "es"
        assert config.voice_model == "nova"
        assert config.preserve_background_audio is False
        assert config.enable_fault_tolerance is False
        assert config.max_retries == 5
        assert config.progress_callback == dummy_callback


class TestPipelineResult:
    
    def test_successful_result(self):
        """测试成功结果"""
        result = PipelineResult(
            job_id="test_job",
            success=True,
            output_file_path="/test/output.mp4",
            processing_time=120.0,
            stages_completed=[ProcessingStage.FILE_VALIDATION, ProcessingStage.AUDIO_EXTRACTION]
        )
        
        assert result.job_id == "test_job"
        assert result.success is True
        assert result.output_file_path == "/test/output.mp4"
        assert result.processing_time == 120.0
        assert len(result.stages_completed) == 2
        assert result.error_message is None
    
    def test_failed_result(self):
        """测试失败结果"""
        result = PipelineResult(
            job_id="test_job",
            success=False,
            error_message="处理失败"
        )
        
        assert result.job_id == "test_job"
        assert result.success is False
        assert result.error_message == "处理失败"
        assert result.output_file_path is None