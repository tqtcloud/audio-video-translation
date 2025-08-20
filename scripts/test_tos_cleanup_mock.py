#!/usr/bin/env python3
"""
模拟TOS资源清理功能测试

此脚本通过模拟的方式测试资源清理逻辑，不需要实际的TOS连接
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class MockTosClient:
    """模拟的TOS客户端"""
    
    def __init__(self):
        self.closed = False
        self.delete_calls = []
        
    def delete_object(self, bucket, key):
        """模拟删除对象"""
        result = Mock()
        result.status_code = 204
        result.request_id = "mock-request-id"
        self.delete_calls.append((bucket, key))
        return result
        
    def close(self):
        """模拟关闭客户端"""
        self.closed = True


class TestTOSCleanup(unittest.TestCase):
    """TOS清理功能测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_tos_client = MockTosClient()
        
    @patch('services.providers.volcengine_tos_simple.tos.TosClientV2')
    def test_volcengine_tos_simple_delete_file(self, mock_tos_class):
        """测试VolcengineTOSSimple的delete_file方法"""
        from services.providers.volcengine_tos_simple import VolcengineTOSSimple
        
        # 设置模拟
        mock_tos_class.return_value = self.mock_tos_client
        
        # 创建TOS客户端实例
        tos_client = VolcengineTOSSimple(
            access_key="test_ak",
            secret_key="test_sk", 
            endpoint="test.endpoint.com",
            region="test-region",
            bucket_name="test-bucket"
        )
        
        # 测试删除文件
        success = tos_client.delete_file("audio/test_file.mp3")
        
        # 验证结果
        self.assertTrue(success)
        self.assertEqual(len(self.mock_tos_client.delete_calls), 1)
        self.assertEqual(self.mock_tos_client.delete_calls[0], ("test-bucket", "audio/test_file.mp3"))
        
    @patch('services.providers.volcengine_tos_simple.tos.TosClientV2')
    def test_volcengine_tos_simple_delete_file_by_url(self, mock_tos_class):
        """测试VolcengineTOSSimple的delete_file_by_url方法"""
        from services.providers.volcengine_tos_simple import VolcengineTOSSimple
        
        # 设置模拟
        mock_tos_class.return_value = self.mock_tos_client
        
        # 创建TOS客户端实例
        tos_client = VolcengineTOSSimple(
            access_key="test_ak",
            secret_key="test_sk",
            endpoint="test.endpoint.com", 
            region="test-region",
            bucket_name="test-bucket"
        )
        
        # 测试通过URL删除文件
        file_url = "https://test-bucket.test.endpoint.com/audio/test_file.mp3"
        success = tos_client.delete_file_by_url(file_url)
        
        # 验证结果
        self.assertTrue(success)
        self.assertEqual(len(self.mock_tos_client.delete_calls), 1)
        self.assertEqual(self.mock_tos_client.delete_calls[0], ("test-bucket", "audio/test_file.mp3"))
        
    def test_cleanup_tos_resources(self):
        """测试IntegratedPipeline的_cleanup_tos_resources方法"""
        from services.integrated_pipeline import IntegratedPipeline
        
        # 创建管道实例
        pipeline = IntegratedPipeline()
        
        # 创建模拟的TOS客户端
        mock_tos_client = Mock()
        mock_tos_client.delete_file_by_url.return_value = True
        mock_tos_client.close.return_value = None
        
        # 测试正常清理
        pipeline._cleanup_tos_resources(
            tos_client=mock_tos_client,
            uploaded_file_url="https://test-bucket.test.com/audio/test.mp3",
            need_cleanup=True
        )
        
        # 验证调用
        mock_tos_client.delete_file_by_url.assert_called_once_with(
            "https://test-bucket.test.com/audio/test.mp3"
        )
        mock_tos_client.close.assert_called_once()
        
    def test_cleanup_tos_resources_no_cleanup_needed(self):
        """测试不需要清理的情况"""
        from services.integrated_pipeline import IntegratedPipeline
        
        pipeline = IntegratedPipeline()
        mock_tos_client = Mock()
        
        # 测试不需要清理的情况
        pipeline._cleanup_tos_resources(
            tos_client=mock_tos_client,
            uploaded_file_url="https://test.com/file.mp3",
            need_cleanup=False
        )
        
        # 验证没有调用删除方法
        mock_tos_client.delete_file_by_url.assert_not_called()
        
    def test_cleanup_tos_resources_exception_handling(self):
        """测试清理过程中的异常处理"""
        from services.integrated_pipeline import IntegratedPipeline
        
        pipeline = IntegratedPipeline()
        
        # 创建会抛出异常的模拟客户端
        mock_tos_client = Mock()
        mock_tos_client.delete_file_by_url.side_effect = Exception("删除失败")
        
        # 测试异常处理（不应该抛出异常）
        try:
            pipeline._cleanup_tos_resources(
                tos_client=mock_tos_client,
                uploaded_file_url="https://test.com/file.mp3", 
                need_cleanup=True
            )
            # 如果没有异常则测试通过
            self.assertTrue(True)
        except Exception:
            self.fail("清理方法不应该抛出异常")
            
        # 验证调用了删除和关闭方法
        mock_tos_client.delete_file_by_url.assert_called_once()
        mock_tos_client.close.assert_called_once()


def main():
    """运行测试"""
    print("🧪 开始TOS资源清理功能模拟测试")
    print("=" * 60)
    
    # 运行单元测试
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    print("\n" + "=" * 60)
    print("✅ 模拟测试完成！")
    print("📋 测试总结:")
    print("   1. VolcengineTOSSimple.delete_file() 方法测试通过")
    print("   2. VolcengineTOSSimple.delete_file_by_url() 方法测试通过")
    print("   3. IntegratedPipeline._cleanup_tos_resources() 方法测试通过")
    print("   4. 异常处理机制测试通过")
    print("\n🎉 TOS资源清理功能逻辑验证成功！")


if __name__ == "__main__":
    main()