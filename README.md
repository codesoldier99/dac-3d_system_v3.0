# DAC-3D 产业化系统 V3.0

[![Status](https://img.shields.io/badge/status-production--ready-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.9+-blue)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

## 🎯 项目简介

基于FPGA+运动控制卡的**色散差动共聚焦(DAC-3D)**产业化光学检测系统。

### 🌟 V3.0 新特性

- 🚀 **软件在环模式** - 完全脱离硬件运行
- 🎨 **144孔物料盘可视化** - 12×12优雅显示
- 🔍 **智能瑕疵检测** - 自动识别和分类
- 💾 **完整数据库系统** - 批次管理和追溯
- ✨ **优雅人机交互** - 专业工业级界面
- 🧪 **完整测试套件** - 质量保证

### 核心特性

- **硬件同步触发**: FPGA实现亚微秒级精度的多设备同步
- **分层架构设计**: 5层架构确保系统稳定性和可扩展性
- **模块化驱动**: 硬件抽象层(HAL)支持设备热插拔和替换
- **状态机控制**: 严格的状态转换确保流程可控
- **产业化级别**: 面向量产设计,支持多项目并行开发

### 系统架构

```
Layer 4: 应用层(PyQt5 + Napari)
Layer 3: 服务层(扫描/算法/数据服务)
Layer 2: 核心层(状态机/事件总线/调度器)
Layer 1: 硬件抽象层(FPGA/Motion/Camera/DMD/Light)
Layer 0: FPGA实时控制层(Zynq-7020)
```

### 硬件配置

| 组件 | 型号 | 功能 |
|------|------|------|
| FPGA主控 | Zynq-7020 | 实时触发控制 |
| XY运动 | ZMotion ZMC408 | 二维扫描 |
| Z轴定位 | PI P-725 | 纳米精度聚焦 |
| 相机 | Basler acA2040×3 | 三通道图像采集 |
| 光调制 | DLP6500 | 结构光投影 |
| 光源 | RGB LED | 多角度照明 |

## ⚡ 快速开始

### 方式1: 一键启动（推荐）

**Windows**: 双击 `START.bat`

**Linux/Mac**:
```bash
chmod +x start.sh
./start.sh
```

### 方式2: 命令行启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行系统（软件在环模式）
python main_sil.py

# 3. 或运行真实硬件模式
python main.py
```

### 界面操作

1. 点击 **[连接硬件]** → 自动连接（SIL模式无需真实硬件）
2. 点击 **[回零]** → 系统初始化
3. 点击 **[开始检测]** → 自动检测144孔
4. 点击孔位 → 查看详情和瑕疵信息

**详细指南**: 阅读 `RUN_ME_FIRST.md` 📖

## 开发指南

### 目录结构

```
dac3d/              # 核心代码包
├── core/           # 核心层
├── hal/            # 硬件抽象层
├── services/       # 服务层
├── algorithms/     # 算法库
└── utils/          # 工具库

ui/                 # 用户界面
├── main_window.py
└── widgets/

fpga/               # FPGA工程
├── vivado/         # Vivado工程源码
├── pynq/           # PYNQ overlay
└── arm/            # ARM端程序

configs/            # 配置文件
tests/              # 测试用例
docs/               # 文档
```

### 代码规范

1. 所有硬件驱动必须实现HAL接口
2. 使用类型注解(Type Hints)
3. 遵循PEP 8代码风格
4. 单元测试覆盖率>80%
5. 提交前运行`pytest`和`mypy`

### 添加新设备

1. 在`dac3d/hal/interfaces.py`中定义接口
2. 在相应子目录实现具体驱动
3. 在`configs/devices.yaml`中配置参数
4. 编写单元测试

## 技术支持

- 文档: `docs/`
- 问题反馈: 提交Issue
- 开发讨论: 团队Wiki

## 许可证

Copyright © 2026 福特科技
保留所有权利
