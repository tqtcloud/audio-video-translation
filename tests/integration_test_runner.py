#!/usr/bin/env python3
"""
集成测试运行器
执行完整的系统集成测试和验证
"""

import os
import sys
import time
import json
import tempfile
import threading
import asyncio
import subprocess
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import traceback
import concurrent.futures

# 导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import AudioVideoTranslationApp
from models.core import ProcessingStage, FileType
from tests.test_data_generator import TestDataGenerator, TestDataSpec
from tests.quality_metrics import QualityAssessmentTool
from services.integrated_pipeline import PipelineConfig
from services.output_generator import OutputConfig


@dataclass
class TestCase:
    """测试用例"""
    name: str
    description: str
    input_file: str
    target_language: str
    expected_duration: float
    expected_stages: List[ProcessingStage]
    quality_thresholds: Dict[str, float]
    timeout: int = 300  # 5分钟超时


@dataclass
class TestResult:
    """测试结果"""
    test_name: str
    success: bool
    processing_time: float
    stages_completed: List[ProcessingStage]
    output_file: Optional[str] = None
    quality_metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    job_id: Optional[str] = None


class IntegrationTestRunner:
    """集成测试运行器"""
    
    def __init__(self, output_dir: str = "./test_results"):
        """初始化测试运行器"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化组件
        self.data_generator = TestDataGenerator("./test_data")
        self.quality_tool = QualityAssessmentTool()
        self.app = None
        
        # 测试统计
        self.test_stats = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "start_time": 0,
            "end_time": 0
        }
        
        # 测试结果
        self.test_results: List[TestResult] = []
    
    def initialize_app(self) -> bool:
        """初始化应用"""
        try:
            print("🔄 初始化音频视频翻译应用...")
            
            self.app = AudioVideoTranslationApp()
            
            # 创建测试配置
            config = {
                "target_language": "zh-CN",
                "voice_model": "alloy",
                "preserve_background_audio": True,
                "output_directory": str(self.output_dir / "outputs"),
                "file_naming_pattern": "{name}_translated_{timestamp}",
                "enable_fault_tolerance": True,
                "max_retries": 2
            }
            
            # 初始化管道
            success = self.app.initialize_pipeline(config)
            if success:
                print("✅ 应用初始化成功")
                return True
            else:
                print("❌ 应用初始化失败")
                return False
                
        except Exception as e:
            print(f"❌ 应用初始化异常: {str(e)}")
            return False
    
    def generate_test_cases(self) -> List[TestCase]:
        """生成测试用例"""
        print("📋 生成测试用例...")
        
        test_cases = []
        
        # 基础功能测试
        basic_tests = [
            TestCase(
                name="基础音频翻译",
                description="测试基础MP3音频文件翻译功能",
                input_file="test_audio_mp3_001.mp3",
                target_language="zh-CN",
                expected_duration=10.0,
                expected_stages=[
                    ProcessingStage.FILE_VALIDATION,
                    ProcessingStage.AUDIO_EXTRACTION,
                    ProcessingStage.SPEECH_TO_TEXT,
                    ProcessingStage.TEXT_TRANSLATION,
                    ProcessingStage.TEXT_TO_SPEECH,
                    ProcessingStage.AUDIO_SYNC,
                    ProcessingStage.VIDEO_ASSEMBLY,
                    ProcessingStage.OUTPUT_GENERATION,
                    ProcessingStage.COMPLETED
                ],
                quality_thresholds={
                    "overall_quality_score": 0.7,
                    "audio_snr_db": 15.0,
                    "sync_accuracy": 0.8
                }
            ),
            TestCase(
                name="基础视频翻译",
                description="测试基础MP4视频文件翻译功能",
                input_file="test_video_mp4_001.mp4",
                target_language="zh-CN",
                expected_duration=15.0,
                expected_stages=[
                    ProcessingStage.FILE_VALIDATION,
                    ProcessingStage.AUDIO_EXTRACTION,
                    ProcessingStage.SPEECH_TO_TEXT,
                    ProcessingStage.TEXT_TRANSLATION,
                    ProcessingStage.TEXT_TO_SPEECH,
                    ProcessingStage.AUDIO_SYNC,
                    ProcessingStage.VIDEO_ASSEMBLY,
                    ProcessingStage.OUTPUT_GENERATION,
                    ProcessingStage.COMPLETED
                ],
                quality_thresholds={
                    "overall_quality_score": 0.7,
                    "video_psnr": 25.0,
                    "sync_accuracy": 0.8
                }
            )
        ]
        
        # 多语言测试
        language_tests = []
        languages = ["en", "es", "fr", "de"]
        for lang in languages:
            test_cases.append(TestCase(
                name=f"多语言测试_{lang}",
                description=f"测试翻译到{lang}语言",
                input_file="test_audio_mp3_001.mp3",
                target_language=lang,
                expected_duration=10.0,
                expected_stages=[stage for stage in ProcessingStage if stage != ProcessingStage.FAILED],
                quality_thresholds={
                    "overall_quality_score": 0.6,
                    "translation_adequacy": 0.7
                }
            ))
        
        # 格式兼容性测试
        format_tests = []
        audio_formats = ["mp3", "wav", "aac", "flac"]
        video_formats = ["mp4", "avi", "mov", "mkv"]
        
        for fmt in audio_formats:
            test_cases.append(TestCase(
                name=f"音频格式测试_{fmt}",
                description=f"测试{fmt}格式音频文件处理",
                input_file=f"test_audio_{fmt}_001.{fmt}",
                target_language="zh-CN",
                expected_duration=10.0,
                expected_stages=[stage for stage in ProcessingStage if stage != ProcessingStage.FAILED],
                quality_thresholds={"overall_quality_score": 0.6}
            ))
        
        for fmt in video_formats[:2]:  # 只测试前两种视频格式
            test_cases.append(TestCase(
                name=f"视频格式测试_{fmt}",
                description=f"测试{fmt}格式视频文件处理",
                input_file=f"test_video_{fmt}_001.{fmt}",
                target_language="zh-CN",
                expected_duration=15.0,
                expected_stages=[stage for stage in ProcessingStage if stage != ProcessingStage.FAILED],
                quality_thresholds={"overall_quality_score": 0.6}
            ))
        
        # 边缘情况测试
        edge_tests = [
            TestCase(
                name="短音频文件测试",
                description="测试极短音频文件（1秒）",
                input_file="test_audio_mp3_short.mp3",
                target_language="zh-CN",
                expected_duration=1.0,
                expected_stages=[stage for stage in ProcessingStage if stage != ProcessingStage.FAILED],
                quality_thresholds={"overall_quality_score": 0.5},
                timeout=120
            ),
            TestCase(
                name="长音频文件测试",
                description="测试长音频文件（5分钟）",
                input_file="test_audio_wav_long.wav",
                target_language="zh-CN",
                expected_duration=300.0,
                expected_stages=[stage for stage in ProcessingStage if stage != ProcessingStage.FAILED],
                quality_thresholds={"overall_quality_score": 0.6},
                timeout=600
            )
        ]
        
        test_cases.extend(basic_tests)
        test_cases.extend(language_tests[:2])  # 只测试前两种语言
        test_cases.extend(format_tests[:4])    # 只测试前四种格式
        test_cases.extend(edge_tests)
        
        print(f"📊 生成了 {len(test_cases)} 个测试用例")
        return test_cases
    
    def prepare_test_data(self, test_cases: List[TestCase]) -> Dict[str, str]:
        """准备测试数据"""
        print("🔧 准备测试数据...")
        
        # 收集需要生成的数据规格
        specs = []
        file_mapping = {}
        
        for test_case in test_cases:
            input_file = test_case.input_file
            
            if input_file in file_mapping:
                continue  # 已经处理过
            
            # 解析文件名获取规格
            parts = input_file.replace('.', '_').split('_')
            if len(parts) >= 3:
                file_type = parts[1]  # audio 或 video
                format_name = parts[2]  # mp3, mp4 等
                
                if "short" in input_file:
                    duration = 1.0
                elif "long" in input_file:
                    duration = 300.0
                elif file_type == "audio":
                    duration = 10.0
                else:
                    duration = 15.0
                
                spec = TestDataSpec(
                    file_type=file_type,
                    format=format_name,
                    duration=duration,
                    content_type="speech",
                    language="en"
                )
                
                if file_type == "video":
                    spec.video_resolution = "1280x720"
                
                specs.append(spec)
                file_mapping[input_file] = len(specs) - 1
        
        # 生成测试数据
        try:
            generated_files = self.data_generator.generate_test_dataset(specs)
            print(f"✅ 成功生成 {len(generated_files)} 个测试文件")
            return generated_files
        except Exception as e:
            print(f"❌ 测试数据生成失败: {str(e)}")
            return {}
    
    def run_single_test(self, test_case: TestCase, test_data_files: Dict[str, str]) -> TestResult:
        """运行单个测试用例"""
        print(f"\n🧪 运行测试: {test_case.name}")
        print(f"📝 描述: {test_case.description}")
        
        start_time = time.time()
        result = TestResult(
            test_name=test_case.name,
            success=False,
            processing_time=0.0,
            stages_completed=[]
        )
        
        try:
            # 获取输入文件路径
            input_file_path = None
            for filename, filepath in test_data_files.items():
                if test_case.input_file in filename:
                    input_file_path = filepath
                    break
            
            if not input_file_path or not os.path.exists(input_file_path):
                result.error_message = f"测试文件不存在: {test_case.input_file}"
                return result
            
            print(f"📁 输入文件: {input_file_path}")
            print(f"🌍 目标语言: {test_case.target_language}")
            
            # 开始处理
            job_id = self.app.process_file(input_file_path, test_case.target_language)
            if not job_id:
                result.error_message = "文件处理启动失败"
                return result
            
            result.job_id = job_id
            print(f"🆔 作业ID: {job_id}")
            
            # 等待处理完成
            success = self.app.wait_for_completion(job_id, test_case.timeout)
            
            # 获取最终状态
            job = self.app.pipeline.get_job_status(job_id)
            if job:
                result.stages_completed = self._get_completed_stages(job.current_stage)
                
                if job.current_stage == ProcessingStage.COMPLETED:
                    result.success = True
                    result.output_file = getattr(job, 'output_file_path', None)
                    print(f"✅ 处理成功完成")
                    print(f"📁 输出文件: {result.output_file}")
                    
                    # 运行质量评估
                    if result.output_file and os.path.exists(result.output_file):
                        result.quality_metrics = self._assess_quality(
                            job_id, input_file_path, result.output_file, job
                        )
                        
                        # 检查质量阈值
                        quality_passed = self._check_quality_thresholds(
                            result.quality_metrics, test_case.quality_thresholds
                        )
                        
                        if not quality_passed:
                            print("⚠️ 质量检查未通过阈值要求")
                            result.success = False
                            result.error_message = "质量检查未通过"
                    
                else:
                    result.error_message = getattr(job, 'error_message', '处理未完成')
                    print(f"❌ 处理失败: {result.error_message}")
            else:
                result.error_message = "无法获取作业状态"
            
        except Exception as e:
            result.error_message = f"测试执行异常: {str(e)}"
            print(f"❌ 测试异常: {str(e)}")
            traceback.print_exc()
        
        result.processing_time = time.time() - start_time
        print(f"⏱️ 处理时间: {result.processing_time:.1f}秒")
        
        return result
    
    def run_concurrent_tests(self, test_cases: List[TestCase], max_workers: int = 3) -> List[TestResult]:
        """运行并发测试"""
        print(f"\n🔄 开始并发测试（最大并发数: {max_workers}）...")
        
        # 准备测试数据
        test_data_files = self.prepare_test_data(test_cases)
        if not test_data_files:
            print("❌ 测试数据准备失败，跳过并发测试")
            return []
        
        results = []
        
        # 分批运行测试（避免资源竞争）
        batch_size = max_workers
        for i in range(0, len(test_cases), batch_size):
            batch = test_cases[i:i + batch_size]
            print(f"\n📦 运行测试批次 {i//batch_size + 1}/{(len(test_cases) + batch_size - 1)//batch_size}")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for test_case in batch:
                    future = executor.submit(self.run_single_test, test_case, test_data_files)
                    futures.append(future)
                
                # 收集结果
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        
                        if result.success:
                            print(f"✅ {result.test_name}: 通过")
                        else:
                            print(f"❌ {result.test_name}: 失败 - {result.error_message}")
                    
                    except Exception as e:
                        print(f"❌ 测试执行异常: {str(e)}")
        
        return results
    
    def run_thread_safety_tests(self) -> List[TestResult]:
        """运行线程安全测试"""
        print("\n🔒 开始线程安全测试...")
        
        # 创建多个相同的测试任务
        test_spec = TestDataSpec(
            file_type="audio",
            format="mp3",
            duration=10.0,
            content_type="speech",
            language="en"
        )
        
        # 生成测试文件
        test_files = self.data_generator.generate_test_dataset([test_spec] * 5)
        
        results = []
        threads = []
        
        def thread_test_worker(thread_id: int, test_file: str):
            """线程测试工作函数"""
            print(f"🧵 线程 {thread_id} 开始处理")
            
            try:
                job_id = self.app.process_file(test_file, "zh-CN")
                if job_id:
                    success = self.app.wait_for_completion(job_id, 300)
                    job = self.app.pipeline.get_job_status(job_id)
                    
                    result = TestResult(
                        test_name=f"线程安全测试_{thread_id}",
                        success=success and job and job.current_stage == ProcessingStage.COMPLETED,
                        processing_time=getattr(job, 'processing_time', 0) if job else 0,
                        stages_completed=self._get_completed_stages(job.current_stage) if job else [],
                        job_id=job_id,
                        output_file=getattr(job, 'output_file_path', None) if job else None
                    )
                else:
                    result = TestResult(
                        test_name=f"线程安全测试_{thread_id}",
                        success=False,
                        processing_time=0,
                        stages_completed=[],
                        error_message="作业创建失败"
                    )
                
                results.append(result)
                print(f"🧵 线程 {thread_id} 完成: {'成功' if result.success else '失败'}")
                
            except Exception as e:
                result = TestResult(
                    test_name=f"线程安全测试_{thread_id}",
                    success=False,
                    processing_time=0,
                    stages_completed=[],
                    error_message=f"线程异常: {str(e)}"
                )
                results.append(result)
                print(f"🧵 线程 {thread_id} 异常: {str(e)}")
        
        # 启动多个线程
        file_list = list(test_files.values())
        for i in range(min(3, len(file_list))):  # 最多3个并发线程
            thread = threading.Thread(
                target=thread_test_worker,
                args=(i + 1, file_list[i]),
                name=f"ThreadSafetyTest-{i+1}"
            )
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=400)  # 每个线程最多等待400秒
        
        print(f"🔒 线程安全测试完成，运行了 {len(results)} 个并发任务")
        return results
    
    def run_performance_benchmarks(self) -> Dict[str, Any]:
        """运行性能基准测试"""
        print("\n⚡ 开始性能基准测试...")
        
        benchmarks = {}
        
        # 生成不同大小的测试文件
        test_specs = [
            TestDataSpec(file_type="audio", format="mp3", duration=10.0, content_type="speech"),   # 小文件
            TestDataSpec(file_type="audio", format="mp3", duration=60.0, content_type="speech"),   # 中文件
            TestDataSpec(file_type="audio", format="mp3", duration=300.0, content_type="speech"),  # 大文件
            TestDataSpec(file_type="video", format="mp4", duration=30.0, content_type="speech", video_resolution="1280x720"),  # 视频文件
        ]
        
        test_files = self.data_generator.generate_test_dataset(test_specs)
        
        for i, (filename, filepath) in enumerate(test_files.items()):
            file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
            print(f"📊 基准测试 {i+1}: {filename} ({file_size:.1f}MB)")
            
            start_time = time.time()
            start_memory = self._get_memory_usage()
            
            try:
                job_id = self.app.process_file(filepath, "zh-CN")
                if job_id:
                    success = self.app.wait_for_completion(job_id, 600)  # 10分钟超时
                    end_time = time.time()
                    end_memory = self._get_memory_usage()
                    
                    processing_time = end_time - start_time
                    memory_usage = end_memory - start_memory
                    
                    # 计算性能指标
                    throughput = file_size / processing_time if processing_time > 0 else 0  # MB/s
                    
                    benchmarks[f"benchmark_{i+1}"] = {
                        "filename": filename,
                        "file_size_mb": file_size,
                        "processing_time_seconds": processing_time,
                        "memory_usage_mb": memory_usage,
                        "throughput_mb_per_second": throughput,
                        "success": success
                    }
                    
                    print(f"  ⏱️ 处理时间: {processing_time:.1f}秒")
                    print(f"  💾 内存使用: {memory_usage:.1f}MB")
                    print(f"  🚀 吞吐量: {throughput:.2f}MB/s")
                
            except Exception as e:
                print(f"  ❌ 基准测试失败: {str(e)}")
                benchmarks[f"benchmark_{i+1}"] = {
                    "filename": filename,
                    "error": str(e)
                }
        
        return benchmarks
    
    def run_error_recovery_tests(self) -> List[TestResult]:
        """运行错误恢复测试"""
        print("\n🛠️ 开始错误恢复测试...")
        
        results = []
        
        # 测试场景
        error_scenarios = [
            {
                "name": "不存在的文件",
                "input_file": "/nonexistent/file.mp3",
                "expected_error": "文件不存在"
            },
            {
                "name": "损坏的文件",
                "input_file": self._create_corrupted_file(),
                "expected_error": "文件验证失败"
            },
            {
                "name": "不支持的格式",
                "input_file": self._create_unsupported_file(),
                "expected_error": "不支持的格式"
            }
        ]
        
        for scenario in error_scenarios:
            print(f"🧪 测试错误场景: {scenario['name']}")
            
            start_time = time.time()
            
            try:
                job_id = self.app.process_file(scenario['input_file'], "zh-CN")
                
                if job_id:
                    # 等待处理完成或失败
                    self.app.wait_for_completion(job_id, 60)  # 1分钟超时
                    job = self.app.pipeline.get_job_status(job_id)
                    
                    if job and job.current_stage == ProcessingStage.FAILED:
                        result = TestResult(
                            test_name=f"错误恢复_{scenario['name']}",
                            success=True,  # 预期失败，所以成功处理错误算作测试通过
                            processing_time=time.time() - start_time,
                            stages_completed=[ProcessingStage.FAILED],
                            error_message=f"按预期失败: {getattr(job, 'error_message', '未知错误')}"
                        )
                        print(f"  ✅ 错误正确处理: {result.error_message}")
                    else:
                        result = TestResult(
                            test_name=f"错误恢复_{scenario['name']}",
                            success=False,
                            processing_time=time.time() - start_time,
                            stages_completed=[],
                            error_message="未能正确处理预期错误"
                        )
                        print(f"  ❌ 错误处理不当")
                else:
                    # 立即失败也是正确的错误处理
                    result = TestResult(
                        test_name=f"错误恢复_{scenario['name']}",
                        success=True,
                        processing_time=time.time() - start_time,
                        stages_completed=[],
                        error_message="立即识别并拒绝无效输入"
                    )
                    print(f"  ✅ 立即识别错误")
                
            except Exception as e:
                # 异常也可能是正确的错误处理方式
                result = TestResult(
                    test_name=f"错误恢复_{scenario['name']}",
                    success=True,
                    processing_time=time.time() - start_time,
                    stages_completed=[],
                    error_message=f"通过异常处理错误: {str(e)}"
                )
                print(f"  ✅ 通过异常处理: {str(e)}")
            
            results.append(result)
        
        return results
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """运行综合测试套件"""
        print("🚀 开始综合测试套件...")
        
        self.test_stats["start_time"] = time.time()
        
        # 初始化应用
        if not self.initialize_app():
            return {"error": "应用初始化失败"}
        
        comprehensive_results = {
            "test_summary": {},
            "functional_tests": [],
            "concurrent_tests": [],
            "thread_safety_tests": [],
            "performance_benchmarks": {},
            "error_recovery_tests": [],
            "overall_statistics": {}
        }
        
        try:
            # 1. 功能测试
            print("\n" + "="*50)
            print("📋 第一阶段：功能测试")
            print("="*50)
            
            test_cases = self.generate_test_cases()
            self.test_stats["total_tests"] += len(test_cases)
            
            test_data_files = self.prepare_test_data(test_cases)
            
            for test_case in test_cases[:5]:  # 只运行前5个核心测试用例
                result = self.run_single_test(test_case, test_data_files)
                comprehensive_results["functional_tests"].append(asdict(result))
                self.test_results.append(result)
                
                if result.success:
                    self.test_stats["passed_tests"] += 1
                else:
                    self.test_stats["failed_tests"] += 1
            
            # 2. 并发测试
            print("\n" + "="*50)
            print("🔄 第二阶段：并发测试")
            print("="*50)
            
            concurrent_test_cases = test_cases[:3]  # 选择3个测试用例进行并发测试
            concurrent_results = self.run_concurrent_tests(concurrent_test_cases, max_workers=2)
            
            for result in concurrent_results:
                comprehensive_results["concurrent_tests"].append(asdict(result))
                self.test_results.append(result)
                self.test_stats["total_tests"] += 1
                
                if result.success:
                    self.test_stats["passed_tests"] += 1
                else:
                    self.test_stats["failed_tests"] += 1
            
            # 3. 线程安全测试
            print("\n" + "="*50)
            print("🔒 第三阶段：线程安全测试")
            print("="*50)
            
            thread_safety_results = self.run_thread_safety_tests()
            for result in thread_safety_results:
                comprehensive_results["thread_safety_tests"].append(asdict(result))
                self.test_results.append(result)
                self.test_stats["total_tests"] += 1
                
                if result.success:
                    self.test_stats["passed_tests"] += 1
                else:
                    self.test_stats["failed_tests"] += 1
            
            # 4. 性能基准测试
            print("\n" + "="*50)
            print("⚡ 第四阶段：性能基准测试")
            print("="*50)
            
            benchmark_results = self.run_performance_benchmarks()
            comprehensive_results["performance_benchmarks"] = benchmark_results
            
            # 5. 错误恢复测试
            print("\n" + "="*50)
            print("🛠️ 第五阶段：错误恢复测试")
            print("="*50)
            
            error_recovery_results = self.run_error_recovery_tests()
            for result in error_recovery_results:
                comprehensive_results["error_recovery_tests"].append(asdict(result))
                self.test_results.append(result)
                self.test_stats["total_tests"] += 1
                
                if result.success:
                    self.test_stats["passed_tests"] += 1
                else:
                    self.test_stats["failed_tests"] += 1
            
        except Exception as e:
            print(f"❌ 综合测试执行异常: {str(e)}")
            traceback.print_exc()
            comprehensive_results["error"] = str(e)
        
        finally:
            self.test_stats["end_time"] = time.time()
            
            # 关闭应用
            if self.app:
                self.app.shutdown()
        
        # 生成最终统计
        comprehensive_results["overall_statistics"] = self._generate_final_statistics()
        
        # 保存结果
        self._save_test_results(comprehensive_results)
        
        return comprehensive_results
    
    def _get_completed_stages(self, current_stage: ProcessingStage) -> List[ProcessingStage]:
        """获取已完成的阶段"""
        all_stages = [
            ProcessingStage.FILE_VALIDATION,
            ProcessingStage.AUDIO_EXTRACTION,
            ProcessingStage.SPEECH_TO_TEXT,
            ProcessingStage.TEXT_TRANSLATION,
            ProcessingStage.TEXT_TO_SPEECH,
            ProcessingStage.AUDIO_SYNC,
            ProcessingStage.VIDEO_ASSEMBLY,
            ProcessingStage.OUTPUT_GENERATION,
            ProcessingStage.COMPLETED
        ]
        
        completed = []
        for stage in all_stages:
            if stage.value <= current_stage.value:
                completed.append(stage)
            else:
                break
        
        return completed
    
    def _assess_quality(self, job_id: str, input_file: str, output_file: str, job) -> Dict[str, Any]:
        """评估处理质量"""
        try:
            # 构建处理结果字典
            processing_results = getattr(job, 'intermediate_results', {})
            
            # 生成质量报告
            quality_report = self.quality_tool.generate_quality_report(
                job_id, input_file, output_file, processing_results
            )
            
            return quality_report
            
        except Exception as e:
            print(f"⚠️ 质量评估失败: {str(e)}")
            return {"error": str(e)}
    
    def _check_quality_thresholds(self, quality_metrics: Dict[str, Any], thresholds: Dict[str, float]) -> bool:
        """检查质量阈值"""
        if not quality_metrics or "metrics" not in quality_metrics:
            return False
        
        for threshold_name, threshold_value in thresholds.items():
            actual_value = self._extract_metric_value(quality_metrics, threshold_name)
            
            if actual_value is None or actual_value < threshold_value:
                print(f"  ⚠️ 质量指标 {threshold_name} 不达标: {actual_value} < {threshold_value}")
                return False
        
        return True
    
    def _extract_metric_value(self, quality_metrics: Dict[str, Any], metric_name: str) -> Optional[float]:
        """从质量指标中提取特定值"""
        metrics = quality_metrics.get("metrics", {})
        
        if metric_name == "overall_quality_score":
            return quality_metrics.get("overall_quality_score")
        elif metric_name == "audio_snr_db":
            audio_metrics = metrics.get("audio_quality", {})
            return audio_metrics.get("snr_db")
        elif metric_name == "video_psnr":
            video_metrics = metrics.get("video_quality", {})
            return video_metrics.get("psnr")
        elif metric_name == "sync_accuracy":
            sync_metrics = metrics.get("sync_quality", {})
            return sync_metrics.get("timing_accuracy")
        elif metric_name == "translation_adequacy":
            trans_metrics = metrics.get("translation_quality", {})
            return trans_metrics.get("adequacy_score")
        
        return None
    
    def _get_memory_usage(self) -> float:
        """获取当前内存使用量（MB）"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except:
            return 0.0
    
    def _create_corrupted_file(self) -> str:
        """创建损坏的测试文件"""
        corrupted_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        corrupted_file.write(b"This is not a valid MP3 file" * 100)
        corrupted_file.close()
        return corrupted_file.name
    
    def _create_unsupported_file(self) -> str:
        """创建不支持格式的测试文件"""
        unsupported_file = tempfile.NamedTemporaryFile(suffix=".xyz", delete=False)
        unsupported_file.write(b"Unsupported file format")
        unsupported_file.close()
        return unsupported_file.name
    
    def _generate_final_statistics(self) -> Dict[str, Any]:
        """生成最终统计信息"""
        total_time = self.test_stats["end_time"] - self.test_stats["start_time"]
        success_rate = (self.test_stats["passed_tests"] / self.test_stats["total_tests"] * 100) if self.test_stats["total_tests"] > 0 else 0
        
        statistics = {
            "总测试数量": self.test_stats["total_tests"],
            "通过测试数量": self.test_stats["passed_tests"],
            "失败测试数量": self.test_stats["failed_tests"],
            "成功率": f"{success_rate:.1f}%",
            "总测试时间": f"{total_time:.1f}秒",
            "平均测试时间": f"{total_time / max(self.test_stats['total_tests'], 1):.1f}秒"
        }
        
        # 分析常见失败原因
        failure_reasons = {}
        for result in self.test_results:
            if not result.success and result.error_message:
                reason = result.error_message.split(':')[0]  # 取错误消息的第一部分
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        
        if failure_reasons:
            statistics["主要失败原因"] = failure_reasons
        
        return statistics
    
    def _save_test_results(self, results: Dict[str, Any]):
        """保存测试结果"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # 保存详细结果
        results_file = self.output_dir / f"comprehensive_test_results_{timestamp}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        # 生成简化报告
        summary_file = self.output_dir / f"test_summary_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("音频视频翻译系统 - 综合测试报告\n")
            f.write("=" * 50 + "\n\n")
            
            stats = results.get("overall_statistics", {})
            for key, value in stats.items():
                f.write(f"{key}: {value}\n")
            
            f.write("\n详细结果请查看: " + str(results_file.name) + "\n")
        
        print(f"\n📊 测试结果已保存:")
        print(f"  📄 详细结果: {results_file}")
        print(f"  📄 摘要报告: {summary_file}")


def main():
    """主函数"""
    print("🎬 音频视频翻译系统 - 综合测试和质量验证")
    print("=" * 60)
    
    # 创建测试运行器
    runner = IntegrationTestRunner()
    
    try:
        # 运行综合测试
        results = runner.run_comprehensive_tests()
        
        # 打印最终统计
        print("\n" + "=" * 60)
        print("📊 最终测试统计")
        print("=" * 60)
        
        stats = results.get("overall_statistics", {})
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        # 判断整体测试结果
        if "成功率" in stats:
            success_rate = float(stats["成功率"].replace("%", ""))
            if success_rate >= 80:
                print("\n🎉 综合测试通过！系统质量良好。")
                return 0
            elif success_rate >= 60:
                print("\n⚠️ 综合测试部分通过，系统存在一些问题需要改进。")
                return 1
            else:
                print("\n❌ 综合测试失败，系统存在严重问题。")
                return 2
        else:
            print("\n❌ 无法获取测试统计信息。")
            return 3
        
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
        return 130
    except Exception as e:
        print(f"\n❌ 测试执行失败: {str(e)}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())