#!/usr/bin/env python3
"""
音频视频翻译系统主入口
提供命令行接口和作业管理功能
"""

import os
import sys
import argparse
import time
import json
from typing import Optional, List, Dict, Any
from dataclasses import asdict

# 加载环境变量（必须在导入其他模块前）
from dotenv import load_dotenv
load_dotenv()

from services.integrated_pipeline import IntegratedPipeline, PipelineConfig, PipelineResult
from services.output_generator import OutputConfig
from models.core import ProcessingStage
from utils.error_handler import handle_error, ErrorContext


class AudioVideoTranslationApp:
    """音频视频翻译应用主类"""
    
    def __init__(self):
        """初始化应用"""
        self.pipeline: Optional[IntegratedPipeline] = None
        self.config_file = "config.json"
        self.default_config = {
            "target_language": "zh-CN",
            "voice_model": "alloy",
            "preserve_background_audio": True,
            "output_directory": "./output",
            "file_naming_pattern": "{name}_translated_{timestamp}",
            "audio_format": "mp3",
            "video_format": "mp4",
            "enable_fault_tolerance": True,
            "max_retries": 3
        }
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """加载配置文件"""
        config_file = config_path or self.config_file
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"✓ 已加载配置文件: {config_file}")
                return {**self.default_config, **config}
            except Exception as e:
                print(f"⚠ 配置文件加载失败，使用默认配置: {str(e)}")
        
        return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any], config_path: Optional[str] = None):
        """保存配置文件"""
        config_file = config_path or self.config_file
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"✓ 配置已保存到: {config_file}")
        except Exception as e:
            print(f"✗ 配置保存失败: {str(e)}")
    
    def initialize_pipeline(self, config: Dict[str, Any]) -> bool:
        """初始化处理管道"""
        try:
            # 创建输出配置
            output_config = OutputConfig(
                output_directory=config.get("output_directory", "./output"),
                file_naming_pattern=config.get("file_naming_pattern", "{name}_translated_{timestamp}"),
                audio_format=config.get("audio_format", "mp3"),
                video_format=config.get("video_format", "mp4"),
                overwrite_existing=config.get("overwrite_existing", False)
            )
            
            # 创建管道配置
            pipeline_config = PipelineConfig(
                target_language=config.get("target_language", "zh-CN"),
                voice_model=config.get("voice_model", "alloy"),
                preserve_background_audio=config.get("preserve_background_audio", True),
                output_config=output_config,
                enable_fault_tolerance=config.get("enable_fault_tolerance", True),
                max_retries=config.get("max_retries", 3),
                progress_callback=self._progress_callback
            )
            
            # 初始化管道
            self.pipeline = IntegratedPipeline(pipeline_config)
            print("✓ 处理管道初始化成功")
            return True
            
        except Exception as e:
            error_context = ErrorContext(operation="initialize_pipeline")
            processed_error = handle_error(e, error_context)
            print(f"✗ 管道初始化失败: {processed_error.user_message}")
            return False
    
    def _progress_callback(self, job_id: str, progress: float, message: str):
        """进度回调函数"""
        print(f"[{job_id[:8]}] {progress:.1%} - {message}")
    
    def process_file(self, file_path: str, target_language: Optional[str] = None) -> Optional[str]:
        """
        处理单个文件
        
        Args:
            file_path: 输入文件路径
            target_language: 目标语言（可选）
            
        Returns:
            作业ID，失败时返回None
        """
        if not self.pipeline:
            print("✗ 管道未初始化，请先运行 init 命令")
            return None
        
        # 检查文件路径：支持HTTP URL和本地文件
        if not file_path.startswith('http') and not os.path.exists(file_path):
            print(f"✗ 文件不存在: {file_path}")
            return None
        
        try:
            print(f"🚀 开始处理文件: {file_path}")
            
            job_id = self.pipeline.process_file(file_path, target_language)
            print(f"✓ 作业已创建，ID: {job_id}")
            
            return job_id
            
        except Exception as e:
            error_context = ErrorContext(
                file_path=file_path,
                operation="process_file"
            )
            processed_error = handle_error(e, error_context)
            print(f"✗ 文件处理失败: {processed_error.user_message}")
            return None
    
    def get_job_status(self, job_id: str) -> bool:
        """获取作业状态"""
        if not self.pipeline:
            print("✗ 管道未初始化")
            return False
        
        try:
            job = self.pipeline.get_job_status(job_id)
            if not job:
                print(f"✗ 作业不存在: {job_id}")
                return False
            
            # 显示作业信息
            print(f"\n📋 作业状态 [{job_id}]")
            print(f"文件路径: {job.file_path}")
            print(f"目标语言: {job.target_language}")
            print(f"当前阶段: {job.current_stage.value}")
            print(f"创建时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(job.created_at))}")
            
            if job.processing_time > 0:
                print(f"处理时间: {job.processing_time:.1f}秒")
            
            if hasattr(job, 'error_message') and job.error_message:
                print(f"错误信息: {job.error_message}")
            
            # 显示进度
            if job.current_stage == ProcessingStage.COMPLETED:
                print("🎉 处理完成!")
                if hasattr(job, 'output_file_path') and job.output_file_path:
                    print(f"输出文件: {job.output_file_path}")
            elif job.current_stage == ProcessingStage.FAILED:
                print("❌ 处理失败")
            else:
                print("⏳ 正在处理中...")
            
            return True
            
        except Exception as e:
            error_context = ErrorContext(
                job_id=job_id,
                operation="get_job_status"
            )
            processed_error = handle_error(e, error_context)
            print(f"✗ 获取状态失败: {processed_error.user_message}")
            return False
    
    def list_jobs(self) -> bool:
        """列出所有作业"""
        if not self.pipeline:
            print("✗ 管道未初始化")
            return False
        
        try:
            # 获取活跃作业
            active_jobs = self.pipeline.list_active_jobs()
            
            # 获取所有作业
            all_jobs = []
            for job_id in self.pipeline.job_manager.jobs:
                job = self.pipeline.job_manager.get_job(job_id)
                if job:
                    all_jobs.append((job_id, job))
            
            if not all_jobs:
                print("📋 暂无作业")
                return True
            
            print(f"\n📋 作业列表 (共 {len(all_jobs)} 个)")
            print("-" * 80)
            print(f"{'作业ID':<12} {'状态':<15} {'文件':<30} {'创建时间':<20}")
            print("-" * 80)
            
            for job_id, job in sorted(all_jobs, key=lambda x: x[1].created_at, reverse=True):
                status = "🔄 处理中" if job_id in active_jobs else self._get_status_emoji(job.current_stage)
                file_name = os.path.basename(job.file_path)
                create_time = time.strftime('%m-%d %H:%M', time.localtime(job.created_at))
                
                print(f"{job_id[:12]:<12} {status:<15} {file_name[:30]:<30} {create_time:<20}")
            
            return True
            
        except Exception as e:
            error_context = ErrorContext(operation="list_jobs")
            processed_error = handle_error(e, error_context)
            print(f"✗ 列出作业失败: {processed_error.user_message}")
            return False
    
    def _get_status_emoji(self, stage: ProcessingStage) -> str:
        """获取状态表情符号"""
        status_map = {
            ProcessingStage.PENDING: "⏳ 等待中",
            ProcessingStage.FILE_VALIDATION: "🔍 验证中",
            ProcessingStage.AUDIO_EXTRACTION: "🎵 提取音频",
            ProcessingStage.SPEECH_TO_TEXT: "📝 转文本",
            ProcessingStage.TEXT_TRANSLATION: "🌐 翻译中",
            ProcessingStage.TEXT_TO_SPEECH: "🗣️ 合成语音",
            ProcessingStage.AUDIO_SYNC: "🔄 同步中",
            ProcessingStage.VIDEO_ASSEMBLY: "🎬 组装中",
            ProcessingStage.OUTPUT_GENERATION: "📦 生成输出",
            ProcessingStage.COMPLETED: "✅ 已完成",
            ProcessingStage.FAILED: "❌ 失败"
        }
        return status_map.get(stage, "❓ 未知")
    
    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        if not self.pipeline:
            print("✗ 管道未初始化")
            return False
        
        try:
            success = self.pipeline.cancel_job(job_id)
            if success:
                print(f"✓ 作业已取消: {job_id}")
            else:
                print(f"✗ 作业取消失败或不存在: {job_id}")
            
            return success
            
        except Exception as e:
            error_context = ErrorContext(
                job_id=job_id,
                operation="cancel_job"
            )
            processed_error = handle_error(e, error_context)
            print(f"✗ 取消作业失败: {processed_error.user_message}")
            return False
    
    def wait_for_completion(self, job_id: str, timeout: int = 300) -> bool:
        """等待作业完成"""
        if not self.pipeline:
            print("✗ 管道未初始化")
            return False
        
        print(f"⏳ 等待作业完成: {job_id} (超时: {timeout}秒)")
        
        start_time = time.time()
        last_stage = None
        
        while time.time() - start_time < timeout:
            try:
                job = self.pipeline.get_job_status(job_id)
                if not job:
                    print(f"✗ 作业不存在: {job_id}")
                    return False
                
                # 显示阶段变化
                if job.current_stage != last_stage:
                    print(f"📍 {self._get_status_emoji(job.current_stage)}")
                    last_stage = job.current_stage
                
                # 检查完成状态
                if job.current_stage == ProcessingStage.COMPLETED:
                    result = self.pipeline.get_processing_result(job_id)
                    print(f"🎉 作业完成! 输出文件: {result.output_file_path}")
                    return True
                elif job.current_stage == ProcessingStage.FAILED:
                    print(f"❌ 作业失败")
                    if hasattr(job, 'error_message') and job.error_message:
                        print(f"错误信息: {job.error_message}")
                    return False
                
                time.sleep(2)  # 等待2秒后重新检查
                
            except KeyboardInterrupt:
                print(f"\n⚠ 用户中断等待")
                return False
            except Exception as e:
                error_context = ErrorContext(
                    job_id=job_id,
                    operation="wait_for_completion"
                )
                processed_error = handle_error(e, error_context)
                print(f"✗ 等待过程中出错: {processed_error.user_message}")
                return False
        
        print(f"⏰ 等待超时 ({timeout}秒)")
        return False
    
    def show_system_metrics(self) -> bool:
        """显示系统指标"""
        if not self.pipeline:
            print("✗ 管道未初始化")
            return False
        
        try:
            metrics = self.pipeline.get_system_metrics()
            
            print("\n📊 系统指标")
            print("-" * 50)
            print(f"活跃作业数量: {metrics['active_jobs_count']}")
            print(f"总处理作业数: {metrics['total_jobs_processed']}")
            
            # 错误统计
            error_stats = metrics['error_statistics']
            if error_stats['total_errors'] > 0:
                print(f"\n错误统计:")
                print(f"  总错误数: {error_stats['total_errors']}")
                if error_stats['by_category']:
                    print("  按分类:")
                    for category, count in error_stats['by_category'].items():
                        print(f"    {category}: {count}")
            
            return True
            
        except Exception as e:
            error_context = ErrorContext(operation="show_system_metrics")
            processed_error = handle_error(e, error_context)
            print(f"✗ 获取指标失败: {processed_error.user_message}")
            return False
    
    def shutdown(self):
        """关闭应用"""
        if self.pipeline:
            print("🔄 正在关闭处理管道...")
            self.pipeline.shutdown()
            print("✓ 应用已关闭")


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="音频视频翻译系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 初始化系统
  python main.py init
  
  # 处理视频文件
  python main.py process input.mp4 --language zh-CN
  
  # 处理音频文件并等待完成
  python main.py process audio.mp3 --wait
  
  # 查看作业状态
  python main.py status JOB_ID
  
  # 列出所有作业
  python main.py list
  
  # 取消作业
  python main.py cancel JOB_ID
  
  # 查看系统指标
  python main.py metrics
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # init 命令
    init_parser = subparsers.add_parser('init', help='初始化系统')
    init_parser.add_argument('--config', help='配置文件路径', default='config.json')
    
    # process 命令
    process_parser = subparsers.add_parser('process', help='处理文件')
    process_parser.add_argument('file', help='输入文件路径')
    process_parser.add_argument('--language', '-l', help='目标语言 (例如: zh-CN, en, es)', default='zh-CN')
    process_parser.add_argument('--wait', '-w', action='store_true', help='等待处理完成')
    process_parser.add_argument('--timeout', '-t', type=int, default=300, help='等待超时时间(秒)')
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='查看作业状态')
    status_parser.add_argument('job_id', help='作业ID')
    
    # list 命令
    subparsers.add_parser('list', help='列出所有作业')
    
    # cancel 命令
    cancel_parser = subparsers.add_parser('cancel', help='取消作业')
    cancel_parser.add_argument('job_id', help='作业ID')
    
    # wait 命令
    wait_parser = subparsers.add_parser('wait', help='等待作业完成')
    wait_parser.add_argument('job_id', help='作业ID')
    wait_parser.add_argument('--timeout', '-t', type=int, default=300, help='超时时间(秒)')
    
    # metrics 命令
    subparsers.add_parser('metrics', help='显示系统指标')
    
    # config 命令
    config_parser = subparsers.add_parser('config', help='配置管理')
    config_subparsers = config_parser.add_subparsers(dest='config_action', help='配置操作')
    
    config_subparsers.add_parser('show', help='显示当前配置')
    
    set_parser = config_subparsers.add_parser('set', help='设置配置项')
    set_parser.add_argument('key', help='配置键')
    set_parser.add_argument('value', help='配置值')
    
    return parser


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    app = AudioVideoTranslationApp()
    
    try:
        if args.command == 'init':
            print("🚀 初始化音频视频翻译系统...")
            config = app.load_config(getattr(args, 'config', None))
            if app.initialize_pipeline(config):
                app.save_config(config, getattr(args, 'config', None))
                print("✅ 系统初始化完成!")
            else:
                print("❌ 系统初始化失败")
                sys.exit(1)
        
        elif args.command == 'process':
            config = app.load_config()
            if not app.initialize_pipeline(config):
                sys.exit(1)
            
            job_id = app.process_file(args.file, args.language)
            if job_id and args.wait:
                app.wait_for_completion(job_id, args.timeout)
        
        elif args.command == 'status':
            config = app.load_config()
            if not app.initialize_pipeline(config):
                sys.exit(1)
            
            app.get_job_status(args.job_id)
        
        elif args.command == 'list':
            config = app.load_config()
            if not app.initialize_pipeline(config):
                sys.exit(1)
            
            app.list_jobs()
        
        elif args.command == 'cancel':
            config = app.load_config()
            if not app.initialize_pipeline(config):
                sys.exit(1)
            
            app.cancel_job(args.job_id)
        
        elif args.command == 'wait':
            config = app.load_config()
            if not app.initialize_pipeline(config):
                sys.exit(1)
            
            app.wait_for_completion(args.job_id, args.timeout)
        
        elif args.command == 'metrics':
            config = app.load_config()
            if not app.initialize_pipeline(config):
                sys.exit(1)
            
            app.show_system_metrics()
        
        elif args.command == 'config':
            if args.config_action == 'show':
                config = app.load_config()
                print("\n📋 当前配置:")
                print(json.dumps(config, indent=2, ensure_ascii=False))
            
            elif args.config_action == 'set':
                config = app.load_config()
                
                # 尝试解析值的类型
                value = args.value
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '').isdigit():
                    value = float(value)
                
                config[args.key] = value
                app.save_config(config)
                print(f"✓ 已设置 {args.key} = {value}")
            
            else:
                parser.parse_args(['config', '--help'])
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n⚠ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        error_context = ErrorContext(operation="main")
        processed_error = handle_error(e, error_context)
        print(f"❌ 应用错误: {processed_error.user_message}")
        sys.exit(1)
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()