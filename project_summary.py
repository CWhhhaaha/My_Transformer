#!/usr/bin/env python3
"""
Project Summary Generator - 生成项目概览
生成完整的项目文件清单和统计信息
"""

import os
from pathlib import Path
from collections import defaultdict

def count_lines(filepath):
    """计算文件行数"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return len(f.readlines())
    except:
        return 0

def get_file_size(filepath):
    """获取文件大小"""
    try:
        return os.path.getsize(filepath)
    except:
        return 0

def format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} GB"

def main():
    project_root = Path(__file__).parent
    
    # 统计信息
    stats = defaultdict(lambda: {"count": 0, "lines": 0, "size": 0})
    all_files = []
    
    # 扫描文件
    for file_path in project_root.glob("**/*"):
        if file_path.is_dir():
            continue
        if "__pycache__" in str(file_path):
            continue
        
        relative_path = file_path.relative_to(project_root)
        suffix = file_path.suffix or "other"
        
        lines = count_lines(file_path)
        size = get_file_size(file_path)
        
        stats[suffix]["count"] += 1
        stats[suffix]["lines"] += lines
        stats[suffix]["size"] += size
        
        all_files.append({
            "path": str(relative_path),
            "suffix": suffix,
            "lines": lines,
            "size": size
        })
    
    # 生成报告
    print("\n" + "="*80)
    print(" " * 20 + "📊 MY_TRANSFORMER 项目概览")
    print("="*80 + "\n")
    
    # 项目位置
    print(f"📁 项目位置: {project_root}")
    print(f"📅 扫描时间: {Path(__file__).stat().st_mtime}\n")
    
    # 文件类型统计
    print("📈 文件类型统计:")
    print("-" * 80)
    print(f"{'文件类型':<15} {'数量':<10} {'总行数':<15} {'总大小':<15}")
    print("-" * 80)
    
    total_files = 0
    total_lines = 0
    total_size = 0
    
    for suffix in sorted(stats.keys()):
        info = stats[suffix]
        total_files += info["count"]
        total_lines += info["lines"]
        total_size += info["size"]
        
        size_str = format_size(info["size"])
        print(f"{suffix:<15} {info['count']:<10} {info['lines']:<15} {size_str:<15}")
    
    print("-" * 80)
    print(f"{'总计':<15} {total_files:<10} {total_lines:<15} {format_size(total_size):<15}")
    print()
    
    # 详细文件清单
    print("\n📋 详细文件清单:")
    print("-" * 80)
    print(f"{'文件名':<45} {'行数':<10} {'大小':<10}")
    print("-" * 80)
    
    for file_info in sorted(all_files, key=lambda x: x["path"]):
        path = file_info["path"]
        lines = file_info["lines"]
        size = format_size(file_info["size"])
        
        # 只显示有意义的文件
        if file_info["suffix"] in [".py", ".md", ".yml", ".txt", ".sh"]:
            print(f"{path:<45} {lines:<10} {size:<10}")
    
    # 核心代码统计
    print("\n\n🔧 核心代码模块:")
    print("-" * 80)
    
    py_files = {
        "config.py": "配置管理系统",
        "model.py": "Transformer核心实现",
        "data.py": "数据加载和词汇管理",
        "train.py": "训练主循环",
        "evaluate.py": "评估和可视化",
        "utils.py": "工具函数库",
        "inference.py": "推理接口",
        "download_dataset.py": "数据集准备",
        "test_complete.py": "完整测试套件",
    }
    
    total_py_lines = 0
    for filename, description in py_files.items():
        py_path = project_root / filename
        if py_path.exists():
            lines = count_lines(py_path)
            total_py_lines += lines
            size = format_size(get_file_size(py_path))
            print(f"  • {filename:<25} {lines:>5} 行  ({size}) - {description}")
    
    print(f"\n  {'Python代码总计':<25} {total_py_lines:>5} 行\n")
    
    # 文档统计
    print("📚 文档文件:")
    print("-" * 80)
    
    doc_files = {
        "README.md": "项目总览（中英文混合）",
        "USAGE_GUIDE_CN.md": "详细使用指南（中文）",
        "PROJECT_COMPLETION_REPORT.md": "项目完成总结报告",
        "INDEX.md": "文件索引和快速导航",
    }
    
    total_doc_lines = 0
    for filename, description in doc_files.items():
        doc_path = project_root / filename
        if doc_path.exists():
            lines = count_lines(doc_path)
            total_doc_lines += lines
            size = format_size(get_file_size(doc_path))
            print(f"  • {filename:<35} {lines:>5} 行  ({size})")
            print(f"    └─ {description}\n")
    
    print(f"  {'文档总计':<35} {total_doc_lines:>5} 行\n")
    
    # 项目结构
    print("📁 项目目录结构:")
    print("-" * 80)
    print("""
  My_Transformer/
  ├── 📄 核心代码文件 (9个)
  │   ├── config.py          ← 配置管理
  │   ├── model.py           ← 模型实现
  │   ├── data.py            ← 数据处理
  │   ├── train.py           ← 训练脚本
  │   ├── evaluate.py        ← 评估脚本
  │   ├── utils.py           ← 工具函数
  │   ├── inference.py       ← 推理脚本
  │   ├── download_dataset.py ← 数据准备
  │   └── test_complete.py   ← 测试套件
  │
  ├── 📚 文档文件 (4个)
  │   ├── README.md          ← 项目说明
  │   ├── USAGE_GUIDE_CN.md  ← 使用指南
  │   ├── PROJECT_COMPLETION_REPORT.md
  │   └── INDEX.md           ← 文件索引
  │
  ├── ⚙️ 配置文件 (3个)
  │   ├── config.py          ← Python配置
  │   ├── environment.yml    ← Conda环境
  │   └── requirements.txt   ← Pip依赖
  │
  ├── 🛠️ 脚本文件 (1个)
  │   └── quickstart.sh      ← 快速启动脚本
  │
  ├── 📂 data/ 数据目录
  │   ├── train.de/en        ← 训练集 (40对)
  │   ├── valid.de/en        ← 验证集 (7对)
  │   └── test.de/en         ← 测试集 (5对)
  │
  ├── 💾 checkpoints/ 模型目录
  │   ├── best_model.pt      ← 最佳模型 ⭐
  │   ├── last_model.pt      ← 最后检查点
  │   └── model_epoch_*.pt   ← 每epoch模型 (10个)
  │
  └── 📊 outputs/ 输出目录
      ├── loss_curve.png        ← 训练曲线
      ├── enc_attn_*.png        ← 编码器注意力 (3个)
      ├── dec_self_*.png        ← 解码器自注意力 (3个)
      ├── cross_attn_*.png      ← 交叉注意力 (3个)
      ├── cross_heads_*.png     ← 多头注意力 (3个)
      ├── rollout_*.png         ← 注意力累积 (3个)
      └── figure_grid_*.png     ← 综合图表 (3个)
    """)
    
    # 功能清单
    print("\n✅ 功能实现清单:")
    print("-" * 80)
    
    features = [
        ("Transformer架构", [
            "✓ 多头自注意力机制 (8个头)",
            "✓ 位置编码",
            "✓ 编码器 (3层)",
            "✓ 解码器 (3层 + 因果掩码)",
            "✓ 前馈网络",
            "✓ Layer Normalization",
            "✓ Dropout正则化",
        ]),
        ("数据处理", [
            "✓ 词汇表构建",
            "✓ 平行语料库加载",
            "✓ 动态填充",
            "✓ 批量处理",
        ]),
        ("训练功能", [
            "✓ Adam优化器",
            "✓ 交叉熵损失",
            "✓ 梯度裁剪",
            "✓ 检查点保存",
            "✓ 验证循环",
        ]),
        ("解码策略", [
            "✓ 贪心解码",
            "✓ Beam Search",
            "✓ 长度归一化",
        ]),
        ("评估工具", [
            "✓ BLEU评分",
            "✓ 损失曲线",
            "✓ 性能指标",
        ]),
        ("可视化", [
            "✓ 训练曲线",
            "✓ 注意力热力图",
            "✓ 多头注意力可视化",
            "✓ 注意力累积图",
        ]),
        ("推理和部署", [
            "✓ 交互式推理",
            "✓ 单句翻译接口",
            "✓ 模型加载",
        ]),
        ("测试和文档", [
            "✓ 单元测试 (7项)",
            "✓ 集成测试",
            "✓ 完整文档",
            "✓ 中文使用指南",
        ]),
    ]
    
    for category, items in features:
        print(f"\n  {category}:")
        for item in items:
            print(f"    {item}")
    
    # 性能指标
    print("\n\n📊 性能指标:")
    print("-" * 80)
    print(f"""
  模型大小:
    • 参数总数: 4,040,824 (~4M)
    • 模型文件: 46 MB
    
  训练速度:
    • 设备: MPS (Apple Silicon)
    • 时间: ~1-2 分钟 (15 epochs)
    • 数据: 40句训练样本
    
  精度指标:
    • 最佳验证损失: 0.8618
    • 测试损失: 1.2124
    • BLEU分数: 0.1219 (在小数据集上)
    """)
    
    # 下一步建议
    print("\n\n🚀 快速开始:")
    print("-" * 80)
    print("""
  1️⃣  激活虚拟环境:
      conda activate transformer_mt
      
  2️⃣  自动化启动 (推荐):
      bash quickstart.sh
      
  3️⃣  或手动步骤:
      python download_dataset.py    # 准备数据
      python test_complete.py       # 运行测试
      python train.py               # 训练模型
      python evaluate.py            # 评估模型
      python inference.py           # 交互推理
    """)
    
    # 文件导航
    print("\n📑 文件导航:")
    print("-" * 80)
    print("""
  快速查找:
    • 配置参数 → config.py
    • 模型代码 → model.py
    • 数据处理 → data.py
    • 训练逻辑 → train.py
    • 推理接口 → inference.py
    • 工具函数 → utils.py
    
  文档查看:
    • 项目说明 → README.md
    • 使用指南 → USAGE_GUIDE_CN.md
    • 完成报告 → PROJECT_COMPLETION_REPORT.md
    • 文件索引 → INDEX.md
    """)
    
    print("\n" + "="*80)
    print(" "*20 + "🎉 项目完成! 现在开始使用吧")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
