"""Core module

精度对齐相关: alignment.py
- ComparisonConstraints: 对比约束定义
- AlignmentThresholds: 预声明阈值
- AlignmentResult / AlignmentReport: 结果与报告
- QWEN25_72B_CONSTRAINTS / BGE_LARGE_ZH_CONSTRAINTS: 预定义模型配置

Profiling 相关: profiling.py
- ProfilingLevel: 采集级别 (L0/L1/L2)
- ProfilingScenario: 采集场景 (训练/推理)
- ProfilingConfig / ProfilingResult: 配置与结果
- generate_profiling_script: 生成采集脚本
- generate_gpu_comparison_script: 生成 GPU 对比脚本
- generate_lightning_callback: PyTorch Lightning Callback
- generate_hf_trainer_callback: HuggingFace Trainer Callback
- setup_profiling_env: 设置性能优化环境变量
- build_profiler_kwargs: 构建 profiler 参数

性能调优相关: perf_tuning.py
- TuningLevel: 调优级别 (pipeline/cpu_affinity/tcmalloc/alloc_conf/compile_*)
- AffinityMode: CPU 绑核模式 (DISABLED/COARSE/FINE)
- TaskQueueMode: 流水优化模式 (DISABLED/ENABLED/ENHANCED)
- AllocStrategy: 内存分配策略 (OFF/EXPANDABLE_SEGMENTS)
- TuningConfig / TuningResult / TuningReport: 配置、结果与报告
- ProgressiveTuningExecutor: 渐进式调优执行器
- apply_tuning_env: 应用调优环境变量
- detect_tcmalloc: 检测 tcmalloc 安装状态
- detect_numa_topology: 检测 NUMA 拓扑
- generate_launch_command: 生成带调优环境变量的启动命令
- generate_python_compile_script: Python 编译优化脚本 (LTO + PGO)
- generate_pytorch_compile_script: PyTorch 编译优化脚本 (LTO + PGO)
- generate_torch_npu_compile_script: torch_npu 编译优化脚本 (LTO + PGO)
- get_recommended_configs: 获取不同场景的推荐调优配置
"""
