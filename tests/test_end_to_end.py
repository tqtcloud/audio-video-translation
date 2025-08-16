import pytest
import tempfile
import os
import json
import subprocess
import time
from unittest.mock import Mock, patch
from main import AudioVideoTranslationApp, create_parser
from services.integrated_pipeline import IntegratedPipeline, PipelineConfig
from models.core import ProcessingStage


class TestAudioVideoTranslationApp:
    
    def setup_method(self):
        self.app = AudioVideoTranslationApp()
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
    
    def teardown_method(self):
        if self.app.pipeline:
            self.app.shutdown()
        
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass
    
    def test_load_config_default(self):
        """测试加载默认配置"""
        config = self.app.load_config("/nonexistent/config.json")
        
        assert config["target_language"] == "zh-CN"
        assert config["voice_model"] == "alloy"
        assert config["preserve_background_audio"] is True
        assert config["output_directory"] == "./output"
    
    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        # 创建测试配置文件
        test_config = {
            "target_language": "es",
            "voice_model": "nova",
            "output_directory": "/custom/output"
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f)
        
        config = self.app.load_config(self.config_file)
        
        assert config["target_language"] == "es"
        assert config["voice_model"] == "nova"
        assert config["output_directory"] == "/custom/output"
        # 应该保留默认值
        assert config["preserve_background_audio"] is True
    
    def test_save_config(self):
        """测试保存配置"""
        test_config = {
            "target_language": "fr",
            "voice_model": "echo"
        }
        
        self.app.save_config(test_config, self.config_file)
        
        # 验证文件已创建并包含正确内容
        assert os.path.exists(self.config_file)
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)
        
        assert saved_config["target_language"] == "fr"
        assert saved_config["voice_model"] == "echo"
    
    @patch('services.integrated_pipeline.IntegratedPipeline')
    def test_initialize_pipeline_success(self, mock_pipeline_class):
        """测试成功初始化管道"""
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        config = self.app.default_config.copy()
        result = self.app.initialize_pipeline(config)
        
        assert result is True
        assert self.app.pipeline == mock_pipeline
        mock_pipeline_class.assert_called_once()
    
    @patch('services.integrated_pipeline.IntegratedPipeline')
    def test_initialize_pipeline_failure(self, mock_pipeline_class):
        """测试管道初始化失败"""
        mock_pipeline_class.side_effect = Exception("初始化失败")
        
        config = self.app.default_config.copy()
        result = self.app.initialize_pipeline(config)
        
        assert result is False
        assert self.app.pipeline is None
    
    def test_process_file_no_pipeline(self):
        """测试没有管道时处理文件"""
        result = self.app.process_file("/test/file.mp4")
        assert result is None
    
    def test_process_file_nonexistent_file(self):
        """测试处理不存在的文件"""
        self.app.pipeline = Mock()
        
        result = self.app.process_file("/nonexistent/file.mp4")
        assert result is None
    
    def test_process_file_success(self):
        """测试成功处理文件"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            mock_pipeline = Mock()
            mock_pipeline.process_file.return_value = "job_123"
            self.app.pipeline = mock_pipeline
            
            result = self.app.process_file(temp_path, "es")
            
            assert result == "job_123"
            mock_pipeline.process_file.assert_called_once_with(temp_path, "es")
        
        finally:
            os.unlink(temp_path)
    
    def test_get_job_status_no_pipeline(self):
        """测试没有管道时获取作业状态"""
        result = self.app.get_job_status("job_123")
        assert result is False
    
    def test_get_job_status_nonexistent_job(self):
        """测试获取不存在作业的状态"""
        mock_pipeline = Mock()
        mock_pipeline.get_job_status.return_value = None
        self.app.pipeline = mock_pipeline
        
        result = self.app.get_job_status("nonexistent_job")
        assert result is False
    
    def test_get_job_status_success(self):
        """测试成功获取作业状态"""
        mock_job = Mock()
        mock_job.file_path = "/test/input.mp4"
        mock_job.target_language = "zh-CN"
        mock_job.current_stage = ProcessingStage.SPEECH_TO_TEXT
        mock_job.created_at = time.time()
        mock_job.processing_time = 60.0
        
        mock_pipeline = Mock()
        mock_pipeline.get_job_status.return_value = mock_job
        self.app.pipeline = mock_pipeline
        
        result = self.app.get_job_status("job_123")
        assert result is True
    
    def test_list_jobs_no_pipeline(self):
        """测试没有管道时列出作业"""
        result = self.app.list_jobs()
        assert result is False
    
    def test_list_jobs_empty(self):
        """测试列出空作业列表"""
        mock_pipeline = Mock()
        mock_pipeline.list_active_jobs.return_value = []
        mock_pipeline.job_manager.jobs = {}
        self.app.pipeline = mock_pipeline
        
        result = self.app.list_jobs()
        assert result is True
    
    def test_list_jobs_with_jobs(self):
        """测试列出包含作业的列表"""
        mock_job = Mock()
        mock_job.file_path = "/test/input.mp4"
        mock_job.current_stage = ProcessingStage.COMPLETED
        mock_job.created_at = time.time()
        
        mock_pipeline = Mock()
        mock_pipeline.list_active_jobs.return_value = []
        mock_pipeline.job_manager.jobs = {"job_123": True}
        mock_pipeline.job_manager.get_job.return_value = mock_job
        self.app.pipeline = mock_pipeline
        
        result = self.app.list_jobs()
        assert result is True
    
    def test_cancel_job_success(self):
        """测试成功取消作业"""
        mock_pipeline = Mock()
        mock_pipeline.cancel_job.return_value = True
        self.app.pipeline = mock_pipeline
        
        result = self.app.cancel_job("job_123")
        assert result is True
    
    def test_cancel_job_failure(self):
        """测试取消作业失败"""
        mock_pipeline = Mock()
        mock_pipeline.cancel_job.return_value = False
        self.app.pipeline = mock_pipeline
        
        result = self.app.cancel_job("nonexistent_job")
        assert result is False
    
    def test_wait_for_completion_success(self):
        """测试等待作业完成成功"""
        # 模拟作业状态变化
        mock_job_pending = Mock()
        mock_job_pending.current_stage = ProcessingStage.SPEECH_TO_TEXT
        
        mock_job_completed = Mock()
        mock_job_completed.current_stage = ProcessingStage.COMPLETED
        
        mock_result = Mock()
        mock_result.output_file_path = "/test/output.mp4"
        
        mock_pipeline = Mock()
        mock_pipeline.get_job_status.side_effect = [mock_job_pending, mock_job_completed]
        mock_pipeline.get_processing_result.return_value = mock_result
        self.app.pipeline = mock_pipeline
        
        # 使用短超时进行测试
        result = self.app.wait_for_completion("job_123", timeout=5)
        assert result is True
    
    def test_wait_for_completion_failure(self):
        """测试等待作业完成失败"""
        mock_job = Mock()
        mock_job.current_stage = ProcessingStage.FAILED
        mock_job.error_message = "处理失败"
        
        mock_pipeline = Mock()
        mock_pipeline.get_job_status.return_value = mock_job
        self.app.pipeline = mock_pipeline
        
        result = self.app.wait_for_completion("job_123", timeout=5)
        assert result is False
    
    def test_show_system_metrics(self):
        """测试显示系统指标"""
        mock_metrics = {
            "active_jobs_count": 2,
            "total_jobs_processed": 10,
            "error_statistics": {
                "total_errors": 1,
                "by_category": {"file_operation": 1}
            }
        }
        
        mock_pipeline = Mock()
        mock_pipeline.get_system_metrics.return_value = mock_metrics
        self.app.pipeline = mock_pipeline
        
        result = self.app.show_system_metrics()
        assert result is True
    
    def test_get_status_emoji(self):
        """测试获取状态表情符号"""
        assert "✅" in self.app._get_status_emoji(ProcessingStage.COMPLETED)
        assert "❌" in self.app._get_status_emoji(ProcessingStage.FAILED)
        assert "⏳" in self.app._get_status_emoji(ProcessingStage.PENDING)
        assert "🔍" in self.app._get_status_emoji(ProcessingStage.FILE_VALIDATION)
    
    def test_progress_callback(self):
        """测试进度回调"""
        # 这个测试主要确保方法不会抛出异常
        self.app._progress_callback("job_123", 0.5, "Processing...")
        # 如果没有异常，测试通过


class TestCommandLineInterface:
    
    def test_create_parser(self):
        """测试创建命令行解析器"""
        parser = create_parser()
        
        # 测试解析不同的命令
        args_init = parser.parse_args(['init'])
        assert args_init.command == 'init'
        
        args_process = parser.parse_args(['process', 'input.mp4', '--language', 'es'])
        assert args_process.command == 'process'
        assert args_process.file == 'input.mp4'
        assert args_process.language == 'es'
        
        args_status = parser.parse_args(['status', 'job_123'])
        assert args_status.command == 'status'
        assert args_status.job_id == 'job_123'
        
        args_list = parser.parse_args(['list'])
        assert args_list.command == 'list'
        
        args_cancel = parser.parse_args(['cancel', 'job_123'])
        assert args_cancel.command == 'cancel'
        assert args_cancel.job_id == 'job_123'
    
    def test_process_command_with_wait(self):
        """测试带等待选项的处理命令"""
        parser = create_parser()
        args = parser.parse_args(['process', 'input.mp4', '--wait', '--timeout', '600'])
        
        assert args.command == 'process'
        assert args.file == 'input.mp4'
        assert args.wait is True
        assert args.timeout == 600
    
    def test_config_commands(self):
        """测试配置命令"""
        parser = create_parser()
        
        args_show = parser.parse_args(['config', 'show'])
        assert args_show.command == 'config'
        assert args_show.config_action == 'show'
        
        args_set = parser.parse_args(['config', 'set', 'target_language', 'es'])
        assert args_set.command == 'config'
        assert args_set.config_action == 'set'
        assert args_set.key == 'target_language'
        assert args_set.value == 'es'


class TestEndToEndScenarios:
    """端到端测试场景"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
    
    def teardown_method(self):
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass
    
    @patch('main.AudioVideoTranslationApp.initialize_pipeline')
    @patch('main.AudioVideoTranslationApp.save_config')
    def test_init_command_flow(self, mock_save_config, mock_init_pipeline):
        """测试初始化命令流程"""
        mock_init_pipeline.return_value = True
        
        # 模拟命令行参数
        import sys
        original_argv = sys.argv
        
        try:
            sys.argv = ['main.py', 'init', '--config', self.config_file]
            
            # 这里我们测试应用逻辑，而不是实际运行main()
            app = AudioVideoTranslationApp()
            config = app.load_config(self.config_file)
            
            # 验证配置加载
            assert config["target_language"] == "zh-CN"
            
            # 模拟初始化成功
            init_result = app.initialize_pipeline(config)
            mock_init_pipeline.assert_called_once()
            
        finally:
            sys.argv = original_argv
    
    @patch('main.AudioVideoTranslationApp.initialize_pipeline')
    @patch('main.AudioVideoTranslationApp.process_file')
    def test_process_command_flow(self, mock_process_file, mock_init_pipeline):
        """测试处理命令流程"""
        mock_init_pipeline.return_value = True
        mock_process_file.return_value = "job_123"
        
        app = AudioVideoTranslationApp()
        
        # 模拟加载配置和初始化
        config = app.load_config()
        init_success = app.initialize_pipeline(config)
        assert init_success
        
        # 模拟处理文件
        job_id = app.process_file("/test/input.mp4", "zh-CN")
        assert job_id == "job_123"
        
        mock_process_file.assert_called_once_with("/test/input.mp4", "zh-CN")
    
    @patch('main.AudioVideoTranslationApp.initialize_pipeline')
    @patch('main.AudioVideoTranslationApp.get_job_status')
    def test_status_command_flow(self, mock_get_status, mock_init_pipeline):
        """测试状态查询命令流程"""
        mock_init_pipeline.return_value = True
        mock_get_status.return_value = True
        
        app = AudioVideoTranslationApp()
        
        # 模拟初始化和状态查询
        config = app.load_config()
        app.initialize_pipeline(config)
        
        status_result = app.get_job_status("job_123")
        assert status_result is True
        
        mock_get_status.assert_called_once_with("job_123")
    
    def test_config_file_management(self):
        """测试配置文件管理"""
        app = AudioVideoTranslationApp()
        
        # 测试保存配置
        test_config = {
            "target_language": "fr",
            "voice_model": "nova",
            "output_directory": "/custom/path"
        }
        
        app.save_config(test_config, self.config_file)
        assert os.path.exists(self.config_file)
        
        # 测试加载配置
        loaded_config = app.load_config(self.config_file)
        assert loaded_config["target_language"] == "fr"
        assert loaded_config["voice_model"] == "nova"
        assert loaded_config["output_directory"] == "/custom/path"
        
        # 验证默认值被保留
        assert "preserve_background_audio" in loaded_config
    
    @patch('services.integrated_pipeline.IntegratedPipeline')
    def test_complete_workflow_simulation(self, mock_pipeline_class):
        """测试完整工作流程模拟"""
        # 设置模拟管道
        mock_pipeline = Mock()
        mock_pipeline.process_file.return_value = "job_123"
        
        mock_job = Mock()
        mock_job.file_path = "/test/input.mp4"
        mock_job.target_language = "zh-CN"
        mock_job.current_stage = ProcessingStage.COMPLETED
        mock_job.created_at = time.time()
        mock_job.processing_time = 120.0
        
        mock_pipeline.get_job_status.return_value = mock_job
        mock_pipeline.list_active_jobs.return_value = []
        mock_pipeline.job_manager.jobs = {"job_123": True}
        mock_pipeline.job_manager.get_job.return_value = mock_job
        
        mock_result = Mock()
        mock_result.output_file_path = "/test/output.mp4"
        mock_pipeline.get_processing_result.return_value = mock_result
        
        mock_pipeline_class.return_value = mock_pipeline
        
        app = AudioVideoTranslationApp()
        
        # 1. 初始化
        config = app.load_config()
        init_success = app.initialize_pipeline(config)
        assert init_success
        
        # 2. 处理文件
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            job_id = app.process_file(temp_path, "zh-CN")
            assert job_id == "job_123"
            
            # 3. 查询状态
            status_success = app.get_job_status(job_id)
            assert status_success
            
            # 4. 列出作业
            list_success = app.list_jobs()
            assert list_success
            
            # 5. 等待完成
            wait_success = app.wait_for_completion(job_id, timeout=1)
            assert wait_success
            
        finally:
            os.unlink(temp_path)
            app.shutdown()


class TestErrorHandling:
    """错误处理测试"""
    
    def test_app_handles_pipeline_init_error(self):
        """测试应用处理管道初始化错误"""
        app = AudioVideoTranslationApp()
        
        with patch('services.integrated_pipeline.IntegratedPipeline', side_effect=Exception("初始化失败")):
            config = app.default_config.copy()
            result = app.initialize_pipeline(config)
            
            assert result is False
            assert app.pipeline is None
    
    def test_app_handles_file_processing_error(self):
        """测试应用处理文件处理错误"""
        app = AudioVideoTranslationApp()
        
        mock_pipeline = Mock()
        mock_pipeline.process_file.side_effect = Exception("处理失败")
        app.pipeline = mock_pipeline
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = app.process_file(temp_path)
            assert result is None
            
        finally:
            os.unlink(temp_path)
    
    def test_app_handles_status_query_error(self):
        """测试应用处理状态查询错误"""
        app = AudioVideoTranslationApp()
        
        mock_pipeline = Mock()
        mock_pipeline.get_job_status.side_effect = Exception("查询失败")
        app.pipeline = mock_pipeline
        
        result = app.get_job_status("job_123")
        assert result is False