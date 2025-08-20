#!/usr/bin/env python3
"""
简单的TOS资源清理功能测试

直接测试清理方法，不依赖完整的管道初始化
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_tos_simple_methods():
    """测试VolcengineTOSSimple的删除方法"""
    print("🧪 测试1: VolcengineTOSSimple删除方法")
    
    try:
        # 创建模拟的TOS客户端
        mock_client = Mock()
        mock_result = Mock()
        mock_result.status_code = 204
        mock_result.request_id = "test-request-id"
        mock_client.delete_object.return_value = mock_result
        
        # 创建VolcengineTOSSimple实例的模拟
        from services.providers.volcengine_tos_simple import VolcengineTOSSimple
        
        # 手动创建实例而不使用构造函数（避免依赖问题）
        tos_instance = object.__new__(VolcengineTOSSimple)
        tos_instance.client = mock_client
        tos_instance.bucket_name = "test-bucket"
        tos_instance.endpoint = "test.endpoint.com"
        
        # 测试delete_file方法
        success = tos_instance.delete_file("audio/test_file.mp3")
        
        # 验证调用
        assert success == True, "delete_file应该返回True"
        mock_client.delete_object.assert_called_with(
            bucket="test-bucket", 
            key="audio/test_file.mp3"
        )
        
        print("✅ delete_file方法测试通过")
        
        # 测试delete_file_by_url方法
        mock_client.reset_mock()  # 重置mock
        mock_client.delete_object.return_value = mock_result
        
        file_url = "https://test-bucket.test.endpoint.com/audio/test_file2.mp3"
        success = tos_instance.delete_file_by_url(file_url)
        
        assert success == True, "delete_file_by_url应该返回True"
        mock_client.delete_object.assert_called_with(
            bucket="test-bucket",
            key="audio/test_file2.mp3"
        )
        
        print("✅ delete_file_by_url方法测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cleanup_tos_resources_standalone():
    """独立测试cleanup_tos_resources方法"""
    print("\n🧪 测试2: 独立清理方法测试")
    
    try:
        from services.integrated_pipeline import IntegratedPipeline
        
        # 创建一个不初始化所有服务的管道实例
        pipeline = object.__new__(IntegratedPipeline)
        
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
        
        print("✅ 正常清理流程测试通过")
        
        # 测试不需要清理的情况
        mock_tos_client.reset_mock()
        
        pipeline._cleanup_tos_resources(
            tos_client=mock_tos_client,
            uploaded_file_url="https://test.com/file.mp3",
            need_cleanup=False  # 不需要清理
        )
        
        # 验证没有调用删除方法
        mock_tos_client.delete_file_by_url.assert_not_called()
        print("✅ 跳过清理流程测试通过")
        
        # 测试异常处理
        mock_tos_client.reset_mock()
        mock_tos_client.delete_file_by_url.side_effect = Exception("删除失败")
        
        # 这应该不会抛出异常
        pipeline._cleanup_tos_resources(
            tos_client=mock_tos_client,
            uploaded_file_url="https://test.com/file.mp3",
            need_cleanup=True
        )
        
        # 验证调用了删除和关闭方法
        mock_tos_client.delete_file_by_url.assert_called_once()
        mock_tos_client.close.assert_called_once()
        
        print("✅ 异常处理测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_url_parsing():
    """测试URL解析功能"""
    print("\n🧪 测试3: URL解析功能")
    
    try:
        from services.providers.volcengine_tos_simple import VolcengineTOSSimple
        
        # 创建实例
        tos_instance = object.__new__(VolcengineTOSSimple)
        tos_instance.bucket_name = "test-bucket"
        tos_instance.endpoint = "test.endpoint.com"
        
        # 模拟delete_file方法
        tos_instance.delete_file = Mock(return_value=True)
        
        # 测试正确的URL格式
        test_url = "https://test-bucket.test.endpoint.com/audio/subfolder/test_file.mp3"
        success = tos_instance.delete_file_by_url(test_url)
        
        # 验证调用
        assert success == True, "URL解析应该成功"
        tos_instance.delete_file.assert_called_with("audio/subfolder/test_file.mp3")
        
        print("✅ URL解析测试通过")
        
        # 测试错误的URL格式
        tos_instance.delete_file.reset_mock()
        wrong_url = "https://wrong-bucket.wrong.endpoint.com/audio/test.mp3"
        success = tos_instance.delete_file_by_url(wrong_url)
        
        assert success == False, "错误的URL应该返回False"
        tos_instance.delete_file.assert_not_called()
        
        print("✅ 错误URL处理测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("🚀 开始TOS资源清理功能简单测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行测试
    test_results.append(test_tos_simple_methods())
    test_results.append(test_cleanup_tos_resources_standalone())  
    test_results.append(test_url_parsing())
    
    # 总结结果
    print("\n" + "=" * 60)
    print("🎯 测试总结:")
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 所有核心功能测试通过！")
        print("\n📋 验证的功能:")
        print("   ✅ TOS文件删除（通过object_key）")
        print("   ✅ TOS文件删除（通过完整URL）")
        print("   ✅ URL解析和object_key提取")
        print("   ✅ 资源清理流程")
        print("   ✅ 清理跳过逻辑")
        print("   ✅ 异常处理机制")
        print("\n🔥 TOS资源清理功能已就绪，可以投入使用！")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)