# CLAUDE.md — DAC-3D 项目规范

本文件指导所有 Claude Code 会话（本地终端、网页云端、`@claude` GitHub Action）如何在本仓库工作。
请遵守以下规范；面向用户交流用中文。

## 项目是什么

基于 FPGA + 运动控制卡的**色散差动共聚焦(DAC-3D)**产业化光学检测系统。
产品定位：**运动卡旁的"视觉同步协处理器"**——不与运动卡竞争，而是增强其生态
（详见 `docs/dac3d-product-strategy.md`）。一台控制器一次只控制一套设备
（XYZ + 相机 + 光源 + DMD），可通过配方复用于不同检测系统。

## 五层架构

```
Layer 4 应用层   ui/ (PyQt5 + Napari)
Layer 3 服务层   dac3d/services/ (scan/algo/data/config/defect)
Layer 2 核心层   dac3d/core/ (state_machine / event_bus / exceptions)
Layer 1 HAL      dac3d/hal/ (interfaces + 各设备驱动 + sim 仿真驱动)
Layer 0 FPGA     fpga/vivado/src/ (Verilog: 时序/PSO/编码器/PWM/触发延迟)
```

## 常用命令

```bash
# 软件在环(无硬件, 开发与教学首选)
pip install -r requirements_sil.txt
python main_sil.py

# 真机模式
pip install -r requirements.txt
python main.py

# 测试与质量
pytest                 # 单元 + 集成测试
mypy dac3d/            # 类型检查
black . && isort .     # 格式化
```

## 代码规范

1. 所有硬件驱动必须实现 `dac3d/hal/interfaces.py` 中的对应接口（`IStage`/`ICamera`/`IDMD`/`ILight`/`IFPGA`/`IEncoderSource`）。
2. 每个真实驱动都要有对应的 `sim` 仿真驱动，保证无硬件可开发与测试。
3. 使用类型注解（Type Hints）；遵循 PEP 8；文档字符串用中文、Google 风格。
4. 单元测试覆盖率目标 >80%；提交前跑 `pytest` 与 `mypy`。
5. 新增设备：接口 → 驱动 → `configs/devices.yaml` 配置 → 单元测试。

## 架构底线（战略强约束，不可让渡）

来自 `docs/dac3d-product-strategy.md` 第 6 节：

1. **运动卡/编码器输入 = 厂商无关的 HAL 边界**：只依赖 `IEncoderSource`，不绑死 ZMC404。
   新增一家运动卡厂商 = 写一个 `IEncoderSource` 驱动 + 一份配方，**不改核心与 FPGA 逻辑**。
   厂商无关通用路径 = `FpgaQuadratureEncoderSource`（编码器差分直入 FPGA）。
2. **触发核永不碰运动**：绝不重实现插补/PLC/安全环，运动域完整留给运动卡。
3. **配方/SDK 层当公开稳定 API 对待**（护城河所在）。
4. **触发时序全部配方驱动、设备无关**：换运动卡/相机/DMD 只改配方与标定。

## 分支与提交

- 在**特性分支**开发，不直接推 `main`。
- 提交信息清晰、说明「做了什么 + 为什么」，可用中文。
- 涉及产品源码的非平凡改动，提交前用 `pytest` 验证。

## 文档索引（docs/）

| 文档 | 内容 |
|------|------|
| `dac3d-product-strategy.md` | 产品战略（视觉同步协处理器定位、护城河、架构底线） |
| `dac3d-hw-highavail-timing-design.md` | 单站控制器：几十纳秒同步 + 高可用 |
| `dac3d-microscopy-platform-hardware.md` | 5–6 站显微检测平台硬件方案、十年路线 |
| `dac3d-aoi-station-bom.md` | 首台光学 AOI 参考站务实档 BOM（型号+参考价） |
| `dac3d-lab-curriculum.md` / `.html` | 半年实践成长计划与闯关地图 |
| `architecture.md` | 系统架构详解 |
| `dataset-management-guide.md` | 数据集管理指南 |
