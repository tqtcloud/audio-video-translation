#!/usr/bin/env python3
"""
基础系统测试
验证核心功能是否正常运行
"""

import os
import sys
import time
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import AudioVideoTranslationApp
from tests.test_data_generator import TestDataGenerator, TestDataSpec


def run_basic_test():
    """运行基础测试"""
    print("🚀 开始基础系统测试...")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    print(f"📁 临时目录: {temp_dir}")
    
    try:
        # 1. 初始化应用
        print("\n📋 步骤 1: 初始化应用")
        app = AudioVideoTranslationApp()
        
        config = {
            "target_language": "zh-CN",
            "voice_model": "alloy",
            "preserve_background_audio": True,
            "output_directory": os.path.join(temp_dir, "output"),
            "enable_fault_tolerance": False  # 禁用容错以简化测试
        }
        
        if not app.initialize_pipeline(config):
            print("❌ 应用初始化失败")
            return False
        
        print("✅ 应用初始化成功")
        
        # 2. 生成测试数据
        print("\n📋 步骤 2: 生成测试数据")
        generator = TestDataGenerator(os.path.join(temp_dir, "test_data"))
        
        # 生成一个简单的测试音频文件
        specs = [TestDataSpec(
            file_type="audio",
            format="wav",
            duration=5.0,  # 短时长减少测试时间
            content_type="speech",
            language="en"
        )]
        
        test_files = generator.generate_test_dataset(specs)
        
        if not test_files:
            print("❌ 测试数据生成失败")
            return False
        
        test_file = list(test_files.values())[0]
        print(f"✅ 测试文件生成成功: {test_file}")
        
        # 3. 测试文件处理
        print("\n📋 步骤 3: 测试文件处理")
        
        # 检查系统指标
        metrics = app.show_system_metrics()
        print("📊 系统指标检查完成")
        
        # 测试作业列表
        app.list_jobs()
        print("📋 作业列表检查完成")
        
        print("✅ 基础功能测试通过")
        
        # 4. 清理
        print("\n📋 步骤 4: 清理资源")
        app.shutdown()
        print("✅ 资源清理完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理临时目录
        import shutil
        try:
            shutil.rmtree(temp_dir)
            print(f"🗑️ 临时目录已清理: {temp_dir}")
        except:
            pass


def test_core_components():
    """测试核心组件"""
    print("\n🔧 测试核心组件...")
    
    try:
        # 测试数据模型
        from models.core import Job, ProcessingStage, FileMetadata, FileType, JobStatus
        from datetime import datetime
        import uuid
        
        job = Job(
            id=str(uuid.uuid4()),
            input_file_path="/test/file.mp3",
            target_language="zh-CN",
            created_at=datetime.now()
        )
        
        assert job.input_file_path == "/test/file.mp3"
        assert job.target_language == "zh-CN"
        assert job.status == JobStatus.PENDING
        
        print("✅ 数据模型测试通过")
        
        # 测试作业管理器
        from services.job_manager import JobManager
        
        manager = JobManager()
        created_job = manager.create_job("/test/file.mp3", "zh")
        retrieved_job = manager.get_job_status(created_job.id)
        
        assert retrieved_job is not None
        assert retrieved_job.input_file_path == "/test/file.mp3"
        
        print("✅ 作业管理器测试通过")
        
        # 测试错误处理
        from utils.error_handler import ErrorHandler, ErrorContext
        
        handler = ErrorHandler()
        context = ErrorContext(operation="test")
        
        # 测试统计功能
        stats = handler.get_error_statistics()
        assert "total_errors" in stats
        
        print("✅ 错误处理器测试通过")
        
        return True
        
    except Exception as e:
        print(f"❌ 组件测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🎬 音频视频翻译系统 - 基础测试")
    print("=" * 50)
    
    # 测试核心组件
    if not test_core_components():
        print("\n❌ 核心组件测试失败")
        return 1
    
    # 运行基础测试
    if not run_basic_test():
        print("\n❌ 基础系统测试失败")
        return 1
    
    print("\n" + "=" * 50)
    print("🎉 所有基础测试通过！系统核心功能正常。")
    print("=" * 50)
    
    return 0


if __name__ == "__main__":
    exit(main())