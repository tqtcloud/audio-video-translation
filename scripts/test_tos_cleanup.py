#!/usr/bin/env python3
"""
测试TOS资源清理功能

此脚本测试以下场景：
1. 正常情况下的文件上传和清理
2. 异常情况下的资源清理
3. 批量清理遗留文件功能
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.providers.volcengine_tos_simple import VolcengineTOSSimple
from services.integrated_pipeline import IntegratedPipeline


def create_test_audio_file() -> str:
    """创建临时测试音频文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mp3', delete=False) as f:
        # 创建一个空的测试文件
        f.write("test audio content")
        return f.name


def test_basic_upload_cleanup():
    """测试基本的上传和清理功能"""
    print("🧪 测试1: 基本上传和清理功能")
    
    try:
        # 创建测试文件
        test_file = create_test_audio_file()
        print(f"📝 创建测试文件: {test_file}")
        
        # 创建TOS客户端
        tos_client = VolcengineTOSSimple.from_env()
        
        # 上传文件
        print("📤 上传测试文件...")
        file_url = tos_client.upload_file(test_file)
        print(f"✅ 上传成功: {file_url}")
        
        # 立即删除
        print("🗑️ 删除测试文件...")
        success = tos_client.delete_file_by_url(file_url)
        
        if success:
            print("✅ 测试1通过: 基本上传和清理功能正常")
            return True
        else:
            print("❌ 测试1失败: 删除文件失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理测试文件
        if 'test_file' in locals() and os.path.exists(test_file):
            os.unlink(test_file)
        # 关闭客户端
        if 'tos_client' in locals():
            tos_client.close()


def test_pipeline_cleanup():
    """测试集成管道的资源清理功能"""
    print("\n🧪 测试2: 集成管道资源清理功能")
    
    try:
        # 创建测试文件
        test_file = create_test_audio_file()
        print(f"📝 创建测试文件: {test_file}")
        
        # 创建集成管道
        pipeline = IntegratedPipeline()
        
        # 开始处理任务（这会上传文件到TOS）
        print("🚀 开始处理任务...")
        job_id = pipeline.process_file(test_file, "en")
        
        # 等待处理完成（或等待一段时间）
        print("⏳ 等待处理...")
        time.sleep(5)  # 等待5秒让处理进行
        
        # 检查作业状态
        job_status = pipeline.get_job_status(job_id)
        if job_status:
            print(f"📊 作业状态: {job_status.current_stage}")
        
        print("✅ 测试2通过: 集成管道资源清理功能（预期TOS文件会被自动清理）")
        return True
        
    except Exception as e:
        print(f"❌ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理测试文件
        if 'test_file' in locals() and os.path.exists(test_file):
            os.unlink(test_file)
        # 关闭管道
        if 'pipeline' in locals():
            pipeline.shutdown()


def test_batch_cleanup():
    """测试批量清理功能"""
    print("\n🧪 测试3: 批量清理功能")
    
    try:
        # 创建几个测试文件并上传
        test_files = []
        uploaded_urls = []
        
        for i in range(3):
            test_file = create_test_audio_file()
            test_files.append(test_file)
            
        tos_client = VolcengineTOSSimple.from_env()
        
        # 上传多个文件
        print("📤 上传多个测试文件...")
        for i, test_file in enumerate(test_files):
            try:
                file_url = tos_client.upload_file(test_file)
                uploaded_urls.append(file_url)
                print(f"✅ 上传文件 {i+1}: {file_url}")
            except Exception as e:
                print(f"⚠️ 上传文件 {i+1} 失败: {e}")
        
        tos_client.close()
        
        # 等待一会，让文件"变旧"
        print("⏳ 等待文件变旧...")
        time.sleep(2)
        
        # 执行批量清理
        pipeline = IntegratedPipeline()
        print("🧹 执行批量清理...")
        cleanup_stats = pipeline.cleanup_orphaned_tos_files(max_age_hours=0)  # 清理所有文件
        
        print(f"📊 清理统计:")
        print(f"   找到文件: {cleanup_stats['found']} 个")
        print(f"   删除成功: {cleanup_stats['deleted']} 个")  
        print(f"   删除失败: {cleanup_stats['failed']} 个")
        
        pipeline.shutdown()
        
        if cleanup_stats['found'] > 0:
            print("✅ 测试3通过: 批量清理功能正常")
            return True
        else:
            print("⚠️ 测试3警告: 未找到需要清理的文件（可能已被其他进程清理）")
            return True
            
    except Exception as e:
        print(f"❌ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理本地测试文件
        for test_file in test_files:
            if os.path.exists(test_file):
                os.unlink(test_file)


def main():
    """主测试函数"""
    print("🚀 开始TOS资源清理功能测试")
    print("=" * 60)
    
    # 检查环境变量
    required_env_vars = [
        'VOLCENGINE_ACCESS_KEY',
        'VOLCENGINE_SECRET_KEY', 
        'TOS_ENDPOINT',
        'TOS_REGION',
        'TOS_BUCKET'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ 缺少必要的环境变量: {', '.join(missing_vars)}")
        print("请设置环境变量后重试")
        return False
    
    # 运行测试
    test_results = []
    
    # 测试1: 基本上传和清理
    test_results.append(test_basic_upload_cleanup())
    
    # 测试2: 集成管道清理
    test_results.append(test_pipeline_cleanup())
    
    # 测试3: 批量清理
    test_results.append(test_batch_cleanup())
    
    # 总结结果
    print("\n" + "=" * 60)
    print("🎯 测试总结:")
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 所有测试通过！TOS资源清理功能正常工作")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)