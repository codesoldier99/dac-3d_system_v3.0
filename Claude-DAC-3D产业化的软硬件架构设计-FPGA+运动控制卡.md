## AC-3D 产业化软硬件架构设计 V1.0

---

### 一、系统总体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              系统总体架构                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Layer 4: 应用层 (Application)                    │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │    │
│  │  │  检测界面  │ │  3D可视化  │ │  报表生成  │ │  远程监控  │           │    │
│  │  │  PyQt5    │ │  Napari   │ │  PDF/Excel│ │  Web API  │           │    │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Layer 3: 服务层 (Services)                       │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │    │
│  │  │  扫描服务  │ │  算法服务  │ │  数据服务  │ │  配置服务  │           │    │
│  │  │ ScanSvc   │ │ AlgoSvc   │ │ DataSvc   │ │ ConfigSvc │           │    │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Layer 2: 核心层 (Core)                           │    │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐       │    │
│  │  │   状态机引擎     │ │    事件总线      │ │    任务调度器    │       │    │
│  │  │ SequenceEngine  │ │   EventBus      │ │   Scheduler     │       │    │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────┘       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Layer 1: 硬件抽象层 (HAL)                        │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │    │
│  │  │ IStage  │ │ ICamera │ │  IDMD   │ │ ILight  │ │ IFPGA   │      │    │
│  │  ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤      │    │
│  │  │ZMotionXY│ │ Basler  │ │ TI_DLP  │ │ RGBLed  │ │ZynqCtrl │      │    │
│  │  │ PIStageZ│ │ HIKVis  │ │         │ │         │ │         │      │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │ Ethernet                              │
├──────────────────────────────────────┼──────────────────────────────────────┤
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Layer 0: FPGA实时控制层                          │    │
│  │                        (Zynq-7020 SoC)                               │    │
│  │  ┌─────────────────────────┐ ┌─────────────────────────┐            │    │
│  │  │    PS (ARM Cortex-A9)   │ │    PL (FPGA Fabric)     │            │    │
│  │  │  ┌───────────────────┐  │ │  ┌───────────────────┐  │            │    │
│  │  │  │ Linux + Python    │  │ │  │  时序控制器        │  │            │    │
│  │  │  │ TCP Server        │  │ │  │  Timing Controller │  │            │    │
│  │  │  │ 参数配置          │  │ │  │                   │  │            │    │
│  │  │  │ 数据预处理        │  │ │  │  位置比较器        │  │            │    │
│  │  │  └───────────────────┘  │ │  │  PSO Generator    │  │            │    │
│  │  │           │ AXI        │ │  │                   │  │            │    │
│  │  │           └────────────┼─┼──┤  PWM控制器        │  │            │    │
│  │  │                        │ │  │  Light Controller │  │            │    │
│  │  └────────────────────────┘ │  │                   │  │            │    │
│  │                              │  │  帧同步计数器     │  │            │    │
│  │                              │  │  Frame Counter   │  │            │    │
│  │                              │  └───────────────────┘  │            │    │
│  │                              └─────────────────────────┘            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │ TTL/LVDS/Analog                       │
├──────────────────────────────────────┼──────────────────────────────────────┤
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     物理设备层 (Physical Devices)                    │    │
│  │                                                                       │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │    │
│  │  │ ZMotion │ │PI压电台 │ │  DMD    │ │ Basler  │ │ RGB LED │       │    │
│  │  │ XY运动  │ │ Z轴     │ │ 图样    │ │ 相机×3  │ │ 光源    │       │    │
│  │  │         │ │         │ │         │ │         │ │         │       │    │
│  │  │ 编码器  │◄┼─────────┼─┼─────────┼─┤ Trigger │◄┤ Trigger │       │    │
│  │  │ 反馈    │ │         │ │ Trigger │◄┼─────────┼─┼─────────┘       │    │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘                   │    │
│  │       │           │           │           │                         │    │
│  │       └───────────┴───────────┴───────────┘                         │    │
│  │                           │                                          │    │
│  │                     FPGA统一触发                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 二、硬件架构详细设计

#### 2.1 硬件选型清单

| 类别               | 组件        | 推荐型号            | 备选型号     | 单价(¥) | 理由                  |
| ------------------ | ----------- | ------------------- | ------------ | -------- | --------------------- |
| **FPGA主控** | SoC开发板   | Zybo Z7-20          | 米联客MZ7020 | 2000     | Zynq-7020，PYNQ支持好 |
| **扩展板**   | 自制IO板    | 定制PCB             | -            | 500      | TTL/差分信号转换      |
| **运动控制** | XY轴控制卡  | ZMC408CE            | 固高GTS      | 8000     | 国产成熟，PSO功能     |
| **精密定位** | Z轴压电台   | PI P-725            | 芯明天PSA    | 30000    | 闭环纳米精度          |
| **图像采集** | 工业相机×3 | Basler acA2040-90um | 海康MV-CA    | 8000/台  | GigE，硬触发          |
| **光调制**   | DMD模组     | DLP6500             | DLP4710      | 15000    | 1920×1080分辨率      |
| **照明**     | RGB LED光源 | 定制穹顶光          | Moritex      | 5000     | 多角度暗场照明        |
| **工控机**   | 上位机      | 研华IPC-610         | 研祥         | 12000    | i7+RTX3060+32G        |

#### 2.2 信号连接拓扑

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              信号连接拓扑图                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│     ┌─────────────┐                              ┌─────────────┐            │
│     │   工控机     │◄─────── GigE ──────────────►│  Basler #1  │            │
│     │  (上位机)    │◄─────── GigE ──────────────►│  Basler #2  │            │
│     │             │◄─────── GigE ──────────────►│  Basler #3  │            │
│     │  Python     │                              └──────┬──────┘            │
│     │  PyQt       │                                     │ Trigger In        │
│     │  CFAN(GPU)  │                                     │ (Line 1)          │
│     └──────┬──────┘                                     │                   │
│            │ Ethernet (TCP)                             │                   │
│            │ 192.168.1.x                                │                   │
│            ▼                                            │                   │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                     Zynq FPGA 板卡                               │    │
│     │  ┌─────────────────────────────────────────────────────────┐   │    │
│     │  │                    FPGA IO 扩展板                        │   │    │
│     │  │                                                          │   │    │
│     │  │   PMOD_A (TTL输出)          PMOD_B (编码器输入)          │   │    │
│     │  │   ┌────┬────┬────┬────┐    ┌────┬────┬────┬────┐       │   │    │
│     │  │   │OUT0│OUT1│OUT2│OUT3│    │ A+ │ A- │ B+ │ B- │       │   │    │
│     │  │   │CAM │DMD │LED │RSV │    │    编码器差分信号    │       │   │    │
│     │  │   └──┬─┴──┬─┴──┬─┴────┘    └──┬─┴────┴────┴──┬─┘       │   │    │
│     │  │      │    │    │               │              │         │   │    │
│     │  └──────┼────┼────┼───────────────┼──────────────┼─────────┘   │    │
│     │         │    │    │               │              │             │    │
│     └─────────┼────┼────┼───────────────┼──────────────┼─────────────┘    │
│               │    │    │               │              │                   │
│               │    │    │               │              │                   │
│               ▼    ▼    ▼               │              │                   │
│     ┌────────────────────────┐          │              │                   │
│     │      信号分配           │          │              │                   │
│     │  OUT0 ──► 相机Trigger   │──────────┼──────────────┘ (已连接上方)     │
│     │  OUT1 ──► DMD Trigger   │          │                                 │
│     │  OUT2 ──► LED PWM       │          │                                 │
│     └────────────────────────┘          │                                 │
│                                          │                                 │
│               ┌──────────────────────────┘                                 │
│               │                                                            │
│               ▼                                                            │
│     ┌─────────────┐         ┌─────────────┐         ┌─────────────┐       │
│     │  ZMotion    │◄─RS485─►│   PI E-709  │         │    DMD      │       │
│     │  ZMC408     │         │   压电控制器 │         │  DLP6500   │       │
│     │             │         │             │         │             │       │
│     │  X轴编码器  │─────────►│  FPGA读取   │         │  Trigger◄──│       │
│     │  Y轴编码器  │         │  (模拟/数字) │         │   (来自FPGA)│       │
│     │             │         │             │         │             │       │
│     │  XY位移台   │         │  Z压电台    │         │  图样投影   │       │
│     └─────────────┘         └─────────────┘         └─────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 2.3 FPGA内部逻辑架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Zynq-7020 内部架构                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      PS (Processing System)                          │    │
│  │                         ARM Cortex-A9                                │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │                    Linux (PetaLinux)                         │   │    │
│  │  │                                                              │   │    │
│  │  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │   │    │
│  │  │   │ TCP Server   │  │ Config Mgr   │  │ Data Buffer  │     │   │    │
│  │  │   │ Port: 5000   │  │ YAML解析     │  │ 环形缓冲区   │     │   │    │
│  │  │   │              │  │              │  │              │     │   │    │
│  │  │   │ 接收指令     │  │ 参数校验     │  │ DMA传输      │     │   │    │
│  │  │   │ 返回状态     │  │ 写入寄存器   │  │ 图像预处理   │     │   │    │
│  │  │   └──────────────┘  └──────────────┘  └──────────────┘     │   │    │
│  │  │                                                              │   │    │
│  │  └──────────────────────────────┬──────────────────────────────┘   │    │
│  │                                  │ AXI-Lite (配置)                  │    │
│  │                                  │ AXI-Stream (数据)                │    │
│  └──────────────────────────────────┼──────────────────────────────────┘    │
│                                      │                                       │
│  ┌──────────────────────────────────┼──────────────────────────────────┐    │
│  │                      PL (Programmable Logic)                         │    │
│  │                                  │                                   │    │
│  │   ┌──────────────────────────────┴───────────────────────────────┐ │    │
│  │   │                    AXI Interconnect                           │ │    │
│  │   └───┬──────────┬──────────┬──────────┬──────────┬──────────────┘ │    │
│  │       │          │          │          │          │                │    │
│  │       ▼          ▼          ▼          ▼          ▼                │    │
│  │  ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐          │    │
│  │  │ 寄存器  ││ 编码器  ││ PSO     ││ PWM     ││ 帧计数  │          │    │
│  │  │ Bank    ││ 解码器  ││ 触发器  ││ 控制器  ││ 器      │          │    │
│  │  │         ││         ││         ││         ││         │          │    │
│  │  │ 0x00:   ││ X轴计数 ││ 位置比较││ CH0:相机││ 触发计数│          │    │
│  │  │ CTRL    ││ Y轴计数 ││ 区间判断││ CH1:DMD ││ 帧号    │          │    │
│  │  │ 0x04:   ││ Z轴计数 ││ TTL生成 ││ CH2:LED ││ 时间戳  │          │    │
│  │  │ STATUS  ││         ││         ││ CH3:RSV ││         │          │    │
│  │  │ 0x08:   ││ 4x      ││         ││         ││         │          │    │
│  │  │ PSO_CFG ││ 倍频    ││ 纳秒级  ││ 16bit   ││ 32bit   │          │    │
│  │  │ ...     ││         ││ 精度    ││ 分辨率  ││ 计数器  │          │    │
│  │  └─────────┘└────┬────┘└────┬────┘└────┬────┘└────┬────┘          │    │
│  │                   │          │          │          │               │    │
│  │   ┌───────────────┴──────────┴──────────┴──────────┴────────────┐ │    │
│  │   │                    Timing State Machine                      │ │    │
│  │   │                      (核心状态机)                             │ │    │
│  │   │                                                              │ │    │
│  │   │   IDLE ──► ARMED ──► SCANNING ──► COMPLETE                  │ │    │
│  │   │     ▲                    │                 │                 │ │    │
│  │   │     └────────────────────┴─────────────────┘                 │ │    │
│  │   │                                                              │ │    │
│  │   │   状态转换由ARM配置，触发逻辑由FPGA自主执行                   │ │    │
│  │   └──────────────────────────────────────────────────────────────┘ │    │
│  │                              │                                     │    │
│  │   ┌──────────────────────────┴────────────────────────────────┐   │    │
│  │   │                      IO Controller                         │   │    │
│  │   │   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐         │   │    │
│  │   │   │PMOD_A  │  │PMOD_B  │  │PMOD_C  │  │ GPIO   │         │   │    │
│  │   │   │TTL OUT │  │ENC IN  │  │ LVDS   │  │ Debug  │         │   │    │
│  │   │   └────────┘  └────────┘  └────────┘  └────────┘         │   │    │
│  │   └───────────────────────────────────────────────────────────┘   │    │
│  │                                                                    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 2.4 FPGA寄存器映射表

| 地址 | 名称         | 读写 | 位宽 | 描述                                          |
| ---- | ------------ | ---- | ---- | --------------------------------------------- |
| 0x00 | CTRL         | RW   | 32   | [0]:全局使能 [1]:软复位 [2]:ARM扫描 [3]:IDLE  |
| 0x04 | STATUS       | RO   | 32   | [0]:忙 [1]:错误 [7:4]:当前状态 [31:16]:帧计数 |
| 0x08 | PSO_START    | RW   | 32   | PSO触发起始位置 (单位: 编码器计数)            |
| 0x0C | PSO_END      | RW   | 32   | PSO触发结束位置                               |
| 0x10 | PSO_INTERVAL | RW   | 32   | PSO触发间隔                                   |
| 0x14 | PSO_MODE     | RW   | 32   | [1:0]:触发模式 0=单次 1=连续 2=往返           |
| 0x18 | PWM_PERIOD   | RW   | 32   | PWM周期 (单位: 10ns)                          |
| 0x1C | PWM_DUTY_0   | RW   | 32   | 通道0占空比 (相机触发脉宽)                    |
| 0x20 | PWM_DUTY_1   | RW   | 32   | 通道1占空比 (DMD触发脉宽)                     |
| 0x24 | PWM_DUTY_2   | RW   | 32   | 通道2占空比 (LED亮度)                         |
| 0x28 | ENC_X_POS    | RO   | 32   | X轴编码器当前位置                             |
| 0x2C | ENC_Y_POS    | RO   | 32   | Y轴编码器当前位置                             |
| 0x30 | ENC_Z_POS    | RO   | 32   | Z轴编码器/模拟量当前位置                      |
| 0x34 | FRAME_CNT    | RO   | 32   | 当前帧计数                                    |
| 0x38 | TIMESTAMP    | RO   | 32   | 时间戳 (单位: μs)                            |
| 0x3C | TRIG_DELAY   | RW   | 32   | 触发延迟补偿 (单位: 10ns)                     |

---

### 三、软件架构详细设计

#### 3.1 目录结构

```
dac3d/
├── README.md
├── pyproject.toml                 # 项目配置
├── requirements.txt
│
├── dac3d/                         # 主包
│   ├── __init__.py
│   │
│   ├── core/                      # 核心层
│   │   ├── __init__.py
│   │   ├── state_machine.py       # 状态机引擎
│   │   ├── event_bus.py           # 事件总线
│   │   ├── scheduler.py           # 任务调度器
│   │   └── exceptions.py          # 自定义异常
│   │
│   ├── hal/                       # 硬件抽象层
│   │   ├── __init__.py
│   │   ├── interfaces.py          # 抽象接口定义
│   │   ├── fpga/                  # FPGA驱动
│   │   │   ├── __init__.py
│   │   │   ├── zynq_controller.py
│   │   │   ├── registers.py
│   │   │   └── protocol.py
│   │   ├── motion/                # 运动控制
│   │   │   ├── __init__.py
│   │   │   ├── zmotion_stage.py
│   │   │   └── pi_piezo.py
│   │   ├── camera/                # 相机驱动
│   │   │   ├── __init__.py
│   │   │   ├── basler_camera.py
│   │   │   └── camera_array.py
│   │   ├── dmd/                   # DMD驱动
│   │   │   ├── __init__.py
│   │   │   └── dlp_controller.py
│   │   ├── light/                 # 光源驱动
│   │   │   ├── __init__.py
│   │   │   └── rgb_light.py
│   │   └── sim/                   # 模拟驱动(测试用)
│   │       ├── __init__.py
│   │       ├── sim_fpga.py
│   │       ├── sim_stage.py
│   │       └── sim_camera.py
│   │
│   ├── services/                  # 服务层
│   │   ├── __init__.py
│   │   ├── scan_service.py        # 扫描服务
│   │   ├── algo_service.py        # 算法服务
│   │   ├── data_service.py        # 数据服务
│   │   └── config_service.py      # 配置服务
│   │
│   ├── algorithms/                # 算法库
│   │   ├── __init__.py
│   │   ├── arc_calibration.py     # ARC标定
│   │   ├── differential.py        # 差动信号处理
│   │   ├── cfan_model.py          # CFAN神经网络
│   │   └── point_cloud.py         # 点云处理
│   │
│   └── utils/                     # 工具库
│       ├── __init__.py
│       ├── logger.py
│       ├── validators.py
│       └── helpers.py
│
├── ui/                            # 用户界面
│   ├── __init__.py
│   ├── main_window.py
│   ├── widgets/
│   │   ├── control_panel.py
│   │   ├── image_viewer.py
│   │   └── parameter_panel.py
│   └── napari_plugin/             # Napari插件
│       ├── __init__.py
│       └── dac3d_widget.py
│
├── configs/                       # 配置文件
│   ├── devices.yaml               # 设备配置
│   ├── system.yaml                # 系统配置
│   └── recipes/                   # 检测配方
│       ├── wedge_filter.yaml
│       └── lcd_panel.yaml
│
├── fpga/                          # FPGA工程
│   ├── vivado/                    # Vivado工程
│   │   ├── dac3d_timing.xpr
│   │   └── src/
│   │       ├── top.v
│   │       ├── timing_ctrl.v
│   │       ├── pso_generator.v
│   │       ├── encoder_decoder.v
│   │       └── pwm_controller.v
│   ├── pynq/                      # PYNQ overlay
│   │   ├── dac3d_timing.bit
│   │   └── dac3d_timing.hwh
│   └── arm/                       # ARM端代码
│       ├── tcp_server.py
│       └── fpga_driver.py
│
├── tests/                         # 测试
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── docs/                          # 文档
    ├── architecture.md
    ├── api_reference.md
    └── user_guide.md
```

#### 3.2 核心接口定义

```python
# dac3d/hal/interfaces.py
"""
硬件抽象层接口定义
所有硬件驱动必须实现这些接口，确保可替换性
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, List, Tuple
import numpy as np


# ============== 数据结构 ==============

@dataclass
class Position:
    """三维位置"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
  
    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class ScanRegion:
    """扫描区域定义"""
    start: Position
    end: Position
    step_x: float
    step_y: float
    step_z: float = 0.0  # Z方向步进（可选）


@dataclass  
class TriggerConfig:
    """触发配置"""
    mode: str = 'position'  # 'position', 'time', 'software'
    start_pos: float = 0.0
    end_pos: float = 1000.0
    interval: float = 10.0  # 位置间隔(μm)或时间间隔(μs)
    pulse_width_ns: int = 1000  # 触发脉冲宽度
    delay_ns: int = 0  # 触发延迟补偿


class DeviceState(Enum):
    """设备状态枚举"""
    DISCONNECTED = auto()
    CONNECTED = auto()
    READY = auto()
    BUSY = auto()
    ERROR = auto()


# ============== 抽象接口 ==============

class IDevice(ABC):
    """所有设备的基类接口"""
  
    @property
    @abstractmethod
    def state(self) -> DeviceState:
        """获取设备状态"""
        pass
  
    @abstractmethod
    def connect(self) -> bool:
        """连接设备"""
        pass
  
    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        pass
  
    @abstractmethod
    def reset(self) -> bool:
        """复位设备"""
        pass


class IStage(IDevice):
    """位移台接口"""
  
    @abstractmethod
    def home(self, axes: str = 'XYZ') -> bool:
        """回零，axes可以是'X','Y','Z','XY','XYZ'等"""
        pass
  
    @abstractmethod
    def move_to(self, pos: Position, wait: bool = True) -> bool:
        """移动到绝对位置"""
        pass
  
    @abstractmethod
    def move_relative(self, delta: Position, wait: bool = True) -> bool:
        """相对移动"""
        pass
  
    @abstractmethod
    def get_position(self) -> Position:
        """获取当前位置"""
        pass
  
    @abstractmethod
    def stop(self) -> bool:
        """紧急停止"""
        pass
  
    @abstractmethod
    def set_velocity(self, velocity: float) -> bool:
        """设置运动速度 (μm/s)"""
        pass
  
    @property
    @abstractmethod
    def is_moving(self) -> bool:
        """是否正在运动"""
        pass


class ICamera(IDevice):
    """相机接口"""
  
    @abstractmethod
    def set_exposure(self, exposure_us: float) -> bool:
        """设置曝光时间(微秒)"""
        pass
  
    @abstractmethod
    def set_gain(self, gain_db: float) -> bool:
        """设置增益(dB)"""
        pass
  
    @abstractmethod
    def set_roi(self, x: int, y: int, width: int, height: int) -> bool:
        """设置感兴趣区域"""
        pass
  
    @abstractmethod
    def set_trigger_mode(self, mode: str) -> bool:
        """设置触发模式: 'software', 'hardware', 'continuous'"""
        pass
  
    @abstractmethod
    def arm(self, n_frames: int = 1) -> bool:
        """准备采集，等待触发"""
        pass
  
    @abstractmethod
    def grab(self, timeout_ms: int = 5000) -> Optional[np.ndarray]:
        """获取单帧图像"""
        pass
  
    @abstractmethod
    def grab_sequence(self, n_frames: int, timeout_ms: int = 30000) -> List[np.ndarray]:
        """获取序列图像"""
        pass
  
    @abstractmethod
    def stop_acquisition(self) -> bool:
        """停止采集"""
        pass
  
    @property
    @abstractmethod
    def frame_rate(self) -> float:
        """当前帧率"""
        pass


class IDMD(IDevice):
    """DMD空间光调制器接口"""
  
    @abstractmethod
    def load_pattern(self, pattern: np.ndarray) -> bool:
        """加载单个图样"""
        pass
  
    @abstractmethod
    def load_sequence(self, patterns: List[np.ndarray]) -> bool:
        """加载图样序列"""
        pass
  
    @abstractmethod
    def set_trigger_mode(self, mode: str) -> bool:
        """设置触发模式: 'software', 'hardware'"""
        pass
  
    @abstractmethod
    def start_sequence(self) -> bool:
        """开始序列播放"""
        pass
  
    @abstractmethod
    def stop_sequence(self) -> bool:
        """停止序列播放"""
        pass
  
    @abstractmethod
    def display_pattern(self, index: int) -> bool:
        """显示指定索引的图样"""
        pass


class ILight(IDevice):
    """光源接口"""
  
    @abstractmethod
    def set_intensity(self, channel: int, intensity: float) -> bool:
        """设置指定通道亮度 (0-100%)"""
        pass
  
    @abstractmethod
    def set_all_intensity(self, r: float, g: float, b: float) -> bool:
        """设置RGB三通道亮度"""
        pass
  
    @abstractmethod
    def on(self, channel: int = -1) -> bool:
        """开启光源，channel=-1表示全部"""
        pass
  
    @abstractmethod
    def off(self, channel: int = -1) -> bool:
        """关闭光源"""
        pass
  
    @abstractmethod
    def set_strobe_mode(self, enable: bool, frequency_hz: float = 0) -> bool:
        """设置频闪模式"""
        pass


class IFPGA(IDevice):
    """FPGA控制器接口 - 核心接口"""
  
    @abstractmethod
    def write_register(self, addr: int, value: int) -> bool:
        """写寄存器"""
        pass
  
    @abstractmethod
    def read_register(self, addr: int) -> int:
        """读寄存器"""
        pass
  
    @abstractmethod
    def configure_pso(self, config: TriggerConfig) -> bool:
        """配置位置同步输出"""
        pass
  
    @abstractmethod
    def configure_pwm(self, channel: int, period_ns: int, duty_ns: int) -> bool:
        """配置PWM输出"""
        pass
  
    @abstractmethod
    def arm_trigger(self) -> bool:
        """触发器进入等待状态"""
        pass
  
    @abstractmethod
    def start_scan(self) -> bool:
        """启动扫描（FPGA开始自主触发）"""
        pass
  
    @abstractmethod
    def stop_scan(self) -> bool:
        """停止扫描"""
        pass
  
    @abstractmethod
    def get_encoder_position(self, axis: str) -> float:
        """获取编码器位置"""
        pass
  
    @abstractmethod
    def get_frame_count(self) -> int:
        """获取已触发帧数"""
        pass
  
    @abstractmethod
    def get_timestamp(self) -> int:
        """获取时间戳(μs)"""
        pass
  
    @abstractmethod
    def set_trigger_callback(self, callback: Callable[[int, int], None]) -> bool:
        """设置触发回调函数，参数为(帧号, 时间戳)"""
        pass


# ============== 组合接口 ==============

class ICameraArray(IDevice):
    """多相机阵列接口"""
  
    @property
    @abstractmethod
    def cameras(self) -> List[ICamera]:
        """获取所有相机"""
        pass
  
    @abstractmethod
    def set_exposure_all(self, exposure_us: float) -> bool:
        """设置所有相机曝光时间"""
        pass
  
    @abstractmethod
    def set_trigger_mode_all(self, mode: str) -> bool:
        """设置所有相机触发模式"""
        pass
  
    @abstractmethod
    def arm_all(self, n_frames: int = 1) -> bool:
        """所有相机准备采集"""
        pass
  
    @abstractmethod
    def grab_all(self, timeout_ms: int = 5000) -> List[Optional[np.ndarray]]:
        """同步获取所有相机图像"""
        pass
  
    @abstractmethod
    def grab_sequence_all(self, n_frames: int, timeout_ms: int = 30000) -> List[List[np.ndarray]]:
        """同步获取所有相机的序列图像"""
        pass
```

#### 3.3 FPGA控制器实现

```python
# dac3d/hal/fpga/zynq_controller.py
"""
Zynq FPGA控制器实现
通过TCP与FPGA板卡上的ARM通信，控制PL逻辑
"""

import socket
import struct
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass

from ..interfaces import IFPGA, DeviceState, TriggerConfig
from .registers import RegisterMap
from .protocol import FPGAProtocol


@dataclass
class ZynqConfig:
    """Zynq配置"""
    ip_address: str = "192.168.1.100"
    port: int = 5000
    timeout_s: float = 5.0


class ZynqController(IFPGA):
    """Zynq FPGA控制器
  
    通过TCP Socket与Zynq板卡上的ARM Linux通信，
    ARM负责解析命令并操作AXI寄存器控制PL逻辑。
  
    通信协议:
        请求: [CMD:1B][ADDR:4B][DATA:4B][CHECKSUM:1B]
        响应: [STATUS:1B][DATA:4B][CHECKSUM:1B]
    """
  
    def __init__(self, config: ZynqConfig = None):
        self._config = config or ZynqConfig()
        self._socket: Optional[socket.socket] = None
        self._state = DeviceState.DISCONNECTED
        self._lock = threading.Lock()
        self._trigger_callback: Optional[Callable[[int, int], None]] = None
        self._callback_thread: Optional[threading.Thread] = None
        self._running = False
  
    @property
    def state(self) -> DeviceState:
        return self._state
  
    def connect(self) -> bool:
        """连接到Zynq板卡"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self._config.timeout_s)
            self._socket.connect((self._config.ip_address, self._config.port))
      
            # 发送握手命令
            if self._handshake():
                self._state = DeviceState.CONNECTED
                self._start_callback_thread()
                return True
            else:
                self._socket.close()
                return False
          
        except Exception as e:
            print(f"FPGA连接失败: {e}")
            self._state = DeviceState.ERROR
            return False
  
    def disconnect(self) -> bool:
        """断开连接"""
        self._running = False
        if self._callback_thread:
            self._callback_thread.join(timeout=2.0)
        if self._socket:
            self._socket.close()
        self._state = DeviceState.DISCONNECTED
        return True
  
    def reset(self) -> bool:
        """复位FPGA"""
        return self.write_register(RegisterMap.CTRL, 0x02)  # 软复位位
  
    def write_register(self, addr: int, value: int) -> bool:
        """写AXI寄存器"""
        with self._lock:
            packet = FPGAProtocol.make_write_packet(addr, value)
            self._socket.sendall(packet)
            response = self._socket.recv(6)
            return FPGAProtocol.parse_response(response)[0] == 0
  
    def read_register(self, addr: int) -> int:
        """读AXI寄存器"""
        with self._lock:
            packet = FPGAProtocol.make_read_packet(addr)
            self._socket.sendall(packet)
            response = self._socket.recv(6)
            status, data = FPGAProtocol.parse_response(response)
            if status == 0:
                return data
            else:
                raise IOError(f"寄存器读取失败, addr={hex(addr)}, status={status}")
  
    def configure_pso(self, config: TriggerConfig) -> bool:
        """配置位置同步输出
  
        Args:
            config: 触发配置
      
        Returns:
            配置是否成功
        """
        # 将物理单位转换为编码器计数
        # 假设编码器分辨率为1μm/count
        encoder_resolution = 1.0  # μm/count，可从配置读取
  
        start_count = int(config.start_pos / encoder_resolution)
        end_count = int(config.end_pos / encoder_resolution)
        interval_count = int(config.interval / encoder_resolution)
  
        success = True
        success &= self.write_register(RegisterMap.PSO_START, start_count)
        success &= self.write_register(RegisterMap.PSO_END, end_count)
        success &= self.write_register(RegisterMap.PSO_INTERVAL, interval_count)
  
        # 配置触发脉冲宽度
        pwm_period = 10000  # 100kHz
        success &= self.write_register(RegisterMap.PWM_PERIOD, pwm_period)
        success &= self.write_register(RegisterMap.PWM_DUTY_0, config.pulse_width_ns // 10)
  
        # 配置触发延迟补偿
        success &= self.write_register(RegisterMap.TRIG_DELAY, config.delay_ns // 10)
  
        return success
  
    def configure_pwm(self, channel: int, period_ns: int, duty_ns: int) -> bool:
        """配置PWM输出"""
        period_reg = period_ns // 10  # 10ns为单位
        duty_reg = duty_ns // 10
  
        self.write_register(RegisterMap.PWM_PERIOD, period_reg)
  
        duty_addr = RegisterMap.PWM_DUTY_0 + channel * 4
        return self.write_register(duty_addr, duty_reg)
  
    def arm_trigger(self) -> bool:
        """触发器进入等待状态"""
        # 读取当前控制寄存器
        ctrl = self.read_register(RegisterMap.CTRL)
        # 设置ARM位
        ctrl |= 0x04  # bit 2: ARM
        return self.write_register(RegisterMap.CTRL, ctrl)
  
    def start_scan(self) -> bool:
        """启动扫描
  
        FPGA将根据PSO配置，在位置到达时自动生成触发信号
        """
        # 确保已经ARM
        status = self.read_register(RegisterMap.STATUS)
        if not (status & 0x04):  # 检查是否已ARM
            self.arm_trigger()
  
        # 设置START位
        ctrl = self.read_register(RegisterMap.CTRL)
        ctrl |= 0x01  # bit 0: ENABLE
        return self.write_register(RegisterMap.CTRL, ctrl)
  
    def stop_scan(self) -> bool:
        """停止扫描"""
        ctrl = self.read_register(RegisterMap.CTRL)
        ctrl &= ~0x01  # 清除ENABLE位
        return self.write_register(RegisterMap.CTRL, ctrl)
  
    def get_encoder_position(self, axis: str) -> float:
        """获取编码器位置 (μm)"""
        addr_map = {
            'X': RegisterMap.ENC_X_POS,
            'Y': RegisterMap.ENC_Y_POS,
            'Z': RegisterMap.ENC_Z_POS,
        }
        if axis.upper() not in addr_map:
            raise ValueError(f"无效的轴: {axis}")
  
        count = self.read_register(addr_map[axis.upper()])
        # 处理有符号数
        if count >= 0x80000000:
            count -= 0x100000000
        return count * 1.0  # 假设1 count = 1 μm
  
    def get_frame_count(self) -> int:
        """获取已触发帧数"""
        return self.read_register(RegisterMap.FRAME_CNT)
  
    def get_timestamp(self) -> int:
        """获取时间戳 (μs)"""
        return self.read_register(RegisterMap.TIMESTAMP)
  
    def set_trigger_callback(self, callback: Callable[[int, int], None]) -> bool:
        """设置触发回调"""
        self._trigger_callback = callback
        return True
  
    def _handshake(self) -> bool:
        """握手确认"""
        packet = FPGAProtocol.make_handshake_packet()
        self._socket.sendall(packet)
        response = self._socket.recv(6)
        status, magic = FPGAProtocol.parse_response(response)
        return status == 0 and magic == 0xDAC3D000
  
    def _start_callback_thread(self):
        """启动回调监听线程"""
        self._running = True
        self._callback_thread = threading.Thread(target=self._callback_loop, daemon=True)
        self._callback_thread.start()
  
    def _callback_loop(self):
        """回调监听循环
  
        FPGA会在每次触发后通过UDP广播帧号和时间戳
        """
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(('', 5001))
        udp_socket.settimeout(0.1)
  
        while self._running:
            try:
                data, addr = udp_socket.recvfrom(16)
                if len(data) == 8:
                    frame_num, timestamp = struct.unpack('<II', data)
                    if self._trigger_callback:
                        self._trigger_callback(frame_num, timestamp)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"回调监听错误: {e}")
                break
  
        udp_socket.close()
```

```python
# dac3d/hal/fpga/registers.py
"""FPGA寄存器地址映射"""

class RegisterMap:
    """寄存器地址常量"""
  
    # 控制寄存器
    CTRL = 0x00           # [0]:使能 [1]:复位 [2]:ARM [3]:IDLE
    STATUS = 0x04         # [0]:忙 [1]:错误 [7:4]:状态 [31:16]:帧计数
  
    # PSO配置
    PSO_START = 0x08      # PSO起始位置
    PSO_END = 0x0C        # PSO结束位置
    PSO_INTERVAL = 0x10   # PSO间隔
    PSO_MODE = 0x14       # PSO模式
  
    # PWM配置
    PWM_PERIOD = 0x18     # PWM周期
    PWM_DUTY_0 = 0x1C     # 通道0占空比(相机)
    PWM_DUTY_1 = 0x20     # 通道1占空比(DMD)
    PWM_DUTY_2 = 0x24     # 通道2占空比(LED)
  
    # 编码器读取
    ENC_X_POS = 0x28      # X轴位置
    ENC_Y_POS = 0x2C      # Y轴位置
    ENC_Z_POS = 0x30      # Z轴位置
  
    # 帧计数和时间戳
    FRAME_CNT = 0x34      # 帧计数
    TIMESTAMP = 0x38      # 时间戳
  
    # 高级配置
    TRIG_DELAY = 0x3C     # 触发延迟


class StatusBits:
    """状态寄存器位定义"""
  
    BUSY = 0x01
    ERROR = 0x02
    ARMED = 0x04
    SCANNING = 0x08
  
    STATE_MASK = 0xF0
    STATE_SHIFT = 4
  
    FRAME_CNT_MASK = 0xFFFF0000
    FRAME_CNT_SHIFT = 16


class CtrlBits:
    """控制寄存器位定义"""
  
    ENABLE = 0x01
    RESET = 0x02
    ARM = 0x04
    IDLE = 0x08
```

```python
# dac3d/hal/fpga/protocol.py
"""FPGA通信协议"""

import struct


class FPGAProtocol:
    """FPGA通信协议编解码"""
  
    # 命令码
    CMD_HANDSHAKE = 0x00
    CMD_READ = 0x01
    CMD_WRITE = 0x02
    CMD_BATCH_READ = 0x03
    CMD_BATCH_WRITE = 0x04
  
    @staticmethod
    def _checksum(data: bytes) -> int:
        """计算校验和"""
        return sum(data) & 0xFF
  
    @classmethod
    def make_handshake_packet(cls) -> bytes:
        """构造握手包"""
        payload = struct.pack('<BII', cls.CMD_HANDSHAKE, 0, 0)
        checksum = cls._checksum(payload)
        return payload + bytes([checksum])
  
    @classmethod
    def make_read_packet(cls, addr: int) -> bytes:
        """构造读请求包"""
        payload = struct.pack('<BII', cls.CMD_READ, addr, 0)
        checksum = cls._checksum(payload)
        return payload + bytes([checksum])
  
    @classmethod
    def make_write_packet(cls, addr: int, value: int) -> bytes:
        """构造写请求包"""
        payload = struct.pack('<BII', cls.CMD_WRITE, addr, value)
        checksum = cls._checksum(payload)
        return payload + bytes([checksum])
  
    @staticmethod
    def parse_response(data: bytes) -> tuple:
        """解析响应包
  
        Returns:
            (status, data): status=0表示成功
        """
        if len(data) != 6:
            raise ValueError(f"响应长度错误: {len(data)}")
  
        status, value, checksum = struct.unpack('<BIB', data)
  
        # 校验
        expected_checksum = (status + (value & 0xFF) + ((value >> 8) & 0xFF) + 
                           ((value >> 16) & 0xFF) + ((value >> 24) & 0xFF)) & 0xFF
        if checksum != expected_checksum:
            raise ValueError("校验和错误")
  
        return status, value
```

#### 3.4 扫描服务实现

```python
# dac3d/services/scan_service.py
"""
扫描服务 - 协调硬件完成各种扫描任务
"""

import threading
import queue
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Callable
import numpy as np

from ..core.state_machine import StateMachine, State
from ..core.event_bus import EventBus, Event
from ..hal.interfaces import (
    IStage, ICameraArray, IDMD, ILight, IFPGA,
    Position, ScanRegion, TriggerConfig
)


class ScanType(Enum):
    """扫描类型"""
    SINGLE_SHOT = auto()      # 单点采集
    Z_STACK = auto()          # Z轴扫描
    XY_MOSAIC = auto()        # XY拼接扫描
    FULL_3D = auto()          # 全3D扫描
    FLY_SCAN = auto()         # 飞拍扫描


@dataclass
class ScanParams:
    """扫描参数"""
    scan_type: ScanType
    region: ScanRegion
    exposure_us: float = 1000.0
    n_averages: int = 1
    z_range: float = 100.0     # Z扫描范围 (μm)
    z_step: float = 1.0        # Z步进 (μm)
    use_autofocus: bool = True
    save_raw: bool = True


@dataclass
class ScanResult:
    """扫描结果"""
    images: List[np.ndarray] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)
    timestamps: List[int] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class ScanState(Enum):
    """扫描状态"""
    IDLE = auto()
    INITIALIZING = auto()
    HOMING = auto()
    CONFIGURING = auto()
    READY = auto()
    SCANNING = auto()
    PROCESSING = auto()
    COMPLETE = auto()
    ERROR = auto()
    ABORTING = auto()


class ScanService:
    """扫描服务
  
    核心职责:
    1. 协调FPGA、相机、位移台等硬件
    2. 管理扫描状态机
    3. 收集和分发扫描数据
    """
  
    def __init__(
        self,
        fpga: IFPGA,
        stage: IStage,
        cameras: ICameraArray,
        dmd: IDMD,
        light: ILight,
        event_bus: EventBus
    ):
        self._fpga = fpga
        self._stage = stage
        self._cameras = cameras
        self._dmd = dmd
        self._light = light
        self._event_bus = event_bus
  
        # 状态机
        self._state = ScanState.IDLE
        self._state_lock = threading.Lock()
  
        # 数据队列
        self._image_queue = queue.Queue(maxsize=1000)
        self._result: Optional[ScanResult] = None
  
        # 回调
        self._progress_callback: Optional[Callable[[int, int], None]] = None
  
        # 线程
        self._scan_thread: Optional[threading.Thread] = None
        self._acquisition_thread: Optional[threading.Thread] = None
        self._abort_flag = threading.Event()
  
    @property
    def state(self) -> ScanState:
        with self._state_lock:
            return self._state
  
    def _set_state(self, new_state: ScanState):
        with self._state_lock:
            old_state = self._state
            self._state = new_state
        self._event_bus.publish(Event('scan_state_changed', {
            'old_state': old_state,
            'new_state': new_state
        }))
  
    def start_scan(self, params: ScanParams) -> bool:
        """启动扫描
  
        Args:
            params: 扫描参数
      
        Returns:
            是否成功启动
        """
        if self.state != ScanState.IDLE:
            print(f"无法启动扫描，当前状态: {self.state}")
            return False
  
        self._abort_flag.clear()
        self._result = ScanResult()
  
        # 启动扫描线程
        self._scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(params,),
            daemon=True
        )
        self._scan_thread.start()
  
        return True
  
    def abort_scan(self) -> bool:
        """中止扫描"""
        if self.state in [ScanState.IDLE, ScanState.COMPLETE]:
            return False
  
        self._abort_flag.set()
        self._set_state(ScanState.ABORTING)
  
        # 停止硬件
        self._fpga.stop_scan()
        self._cameras.stop_acquisition_all()
        self._stage.stop()
  
        return True
  
    def get_result(self) -> Optional[ScanResult]:
        """获取扫描结果"""
        return self._result
  
    def set_progress_callback(self, callback: Callable[[int, int], None]):
        """设置进度回调 (current, total)"""
        self._progress_callback = callback
  
    def _scan_worker(self, params: ScanParams):
        """扫描工作线程"""
        try:
            # 1. 初始化
            self._set_state(ScanState.INITIALIZING)
            self._initialize_hardware(params)
      
            if self._abort_flag.is_set():
                return
      
            # 2. 回零
            self._set_state(ScanState.HOMING)
            if not self._stage.home():
                raise RuntimeError("位移台回零失败")
      
            if self._abort_flag.is_set():
                return
      
            # 3. 配置硬件
            self._set_state(ScanState.CONFIGURING)
            self._configure_hardware(params)
      
            if self._abort_flag.is_set():
                return
      
            # 4. 执行扫描
            self._set_state(ScanState.SCANNING)
      
            if params.scan_type == ScanType.FLY_SCAN:
                self._execute_fly_scan(params)
            elif params.scan_type == ScanType.Z_STACK:
                self._execute_z_stack(params)
            elif params.scan_type == ScanType.XY_MOSAIC:
                self._execute_xy_mosaic(params)
            else:
                self._execute_single_shot(params)
      
            if self._abort_flag.is_set():
                return
      
            # 5. 完成
            self._set_state(ScanState.COMPLETE)
            self._event_bus.publish(Event('scan_complete', {'result': self._result}))
      
        except Exception as e:
            self._set_state(ScanState.ERROR)
            self._event_bus.publish(Event('scan_error', {'error': str(e)}))
            print(f"扫描错误: {e}")
  
        finally:
            self._cleanup_hardware()
            if self.state not in [ScanState.COMPLETE, ScanState.ERROR]:
                self._set_state(ScanState.IDLE)
  
    def _initialize_hardware(self, params: ScanParams):
        """初始化硬件"""
        # 确保所有设备已连接
        if not self._fpga.state.CONNECTED:
            if not self._fpga.connect():
                raise RuntimeError("FPGA连接失败")
  
        # 复位FPGA
        self._fpga.reset()
  
        # 设置相机参数
        self._cameras.set_exposure_all(params.exposure_us)
        self._cameras.set_trigger_mode_all('hardware')
  
        # 开启光源
        self._light.on()
  
    def _configure_hardware(self, params: ScanParams):
        """配置硬件参数"""
        region = params.region
  
        # 计算扫描点数
        n_points_x = int((region.end.x - region.start.x) / region.step_x) + 1
        n_points_y = int((region.end.y - region.start.y) / region.step_y) + 1
  
        # 配置FPGA PSO
        trigger_config = TriggerConfig(
            mode='position',
            start_pos=region.start.x,
            end_pos=region.end.x,
            interval=region.step_x,
            pulse_width_ns=1000,
            delay_ns=0
        )
        self._fpga.configure_pso(trigger_config)
  
        # 配置PWM（LED亮度）
        self._fpga.configure_pwm(channel=2, period_ns=10000, duty_ns=5000)  # 50%亮度
  
        # 设置位移台速度
        velocity = region.step_x * 100  # 100 points/s
        self._stage.set_velocity(velocity)
  
        # 保存元数据
        self._result.metadata = {
            'scan_type': params.scan_type.name,
            'n_points_x': n_points_x,
            'n_points_y': n_points_y,
            'region': region,
            'exposure_us': params.exposure_us,
        }
  
    def _execute_fly_scan(self, params: ScanParams):
        """执行飞拍扫描
  
        这是DAC-3D的核心扫描模式:
        1. FPGA根据编码器位置自动触发
        2. 相机硬触发采集
        3. Python异步收取图像
        """
        region = params.region
        n_points_x = int((region.end.x - region.start.x) / region.step_x) + 1
        n_lines_y = int((region.end.y - region.start.y) / region.step_y) + 1
        total_frames = n_points_x * n_lines_y * len(self._cameras.cameras)
  
        # 设置触发回调
        frame_count = [0]
  
        def on_trigger(frame_num, timestamp):
            frame_count[0] = frame_num
            if self._progress_callback:
                self._progress_callback(frame_num, total_frames // 3)
  
        self._fpga.set_trigger_callback(on_trigger)
  
        # 启动图像采集线程
        self._acquisition_thread = threading.Thread(
            target=self._acquisition_worker,
            args=(n_points_x * n_lines_y,),
            daemon=True
        )
        self._acquisition_thread.start()
  
        # 逐行扫描
        for line_idx in range(n_lines_y):
            if self._abort_flag.is_set():
                break
      
            # 移动到行起点
            y_pos = region.start.y + line_idx * region.step_y
            self._stage.move_to(Position(x=region.start.x, y=y_pos), wait=True)
      
            # 相机准备
            self._cameras.arm_all(n_frames=n_points_x)
      
            # FPGA准备并启动
            self._fpga.arm_trigger()
            self._fpga.start_scan()
      
            # 位移台开始匀速运动（FPGA会自动触发）
            self._stage.move_to(Position(x=region.end.x, y=y_pos), wait=True)
      
            # 等待FPGA完成
            while self._fpga.get_frame_count() < n_points_x * (line_idx + 1):
                if self._abort_flag.is_set():
                    break
                time.sleep(0.01)
      
            # 收取本行图像
            images = self._cameras.grab_sequence_all(n_points_x)
            for i, imgs in enumerate(zip(*images)):  # 转置为按帧组织
                self._result.images.append(imgs)
                self._result.positions.append(Position(
                    x=region.start.x + i * region.step_x,
                    y=y_pos
                ))
  
        # 停止扫描
        self._fpga.stop_scan()
  
        # 等待采集线程结束
        self._acquisition_thread.join(timeout=5.0)
  
    def _execute_z_stack(self, params: ScanParams):
        """执行Z轴扫描"""
        z_start = -params.z_range / 2
        z_end = params.z_range / 2
        n_steps = int(params.z_range / params.z_step)
  
        for i in range(n_steps):
            if self._abort_flag.is_set():
                break
      
            z_pos = z_start + i * params.z_step
            self._stage.move_to(Position(z=z_pos), wait=True)
      
            # 软件触发单帧采集
            self._cameras.arm_all(n_frames=1)
            images = self._cameras.grab_all()
      
            self._result.images.append(images)
            self._result.positions.append(Position(z=z_pos))
      
            if self._progress_callback:
                self._progress_callback(i + 1, n_steps)
  
    def _execute_xy_mosaic(self, params: ScanParams):
        """执行XY拼接扫描"""
        region = params.region
  
        x_positions = np.arange(region.start.x, region.end.x + 0.001, region.step_x)
        y_positions = np.arange(region.start.y, region.end.y + 0.001, region.step_y)
        total = len(x_positions) * len(y_positions)
  
        count = 0
        for y in y_positions:
            for x in x_positions:
                if self._abort_flag.is_set():
                    return
          
                self._stage.move_to(Position(x=x, y=y), wait=True)
          
                self._cameras.arm_all(n_frames=1)
                images = self._cameras.grab_all()
          
                self._result.images.append(images)
                self._result.positions.append(Position(x=x, y=y))
          
                count += 1
                if self._progress_callback:
                    self._progress_callback(count, total)
  
    def _execute_single_shot(self, params: ScanParams):
        """执行单点采集"""
        self._cameras.arm_all(n_frames=1)
        images = self._cameras.grab_all()
  
        self._result.images.append(images)
        self._result.positions.append(self._stage.get_position())
  
        if self._progress_callback:
            self._progress_callback(1, 1)
  
    def _acquisition_worker(self, expected_frames: int):
        """图像采集工作线程"""
        received = 0
        while received < expected_frames and not self._abort_flag.is_set():
            try:
                # 这里可以做预处理或直接写入磁盘
                time.sleep(0.001)
                received = len(self._result.images)
            except Exception as e:
                print(f"采集线程错误: {e}")
                break
  
    def _cleanup_hardware(self):
        """清理硬件状态"""
        self._fpga.stop_scan()
        self._cameras.stop_acquisition_all()
        self._light.off()
```

#### 3.5 算法服务实现

```python
# dac3d/services/algo_service.py
"""
算法服务 - 封装DAC-3D核心算法
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
import threading
from concurrent.futures import ThreadPoolExecutor

# GPU加速（可选）
try:
    import cupy as cp
    HAS_CUDA = True
except ImportError:
    HAS_CUDA = False
    cp = np


@dataclass
class ARCConfig:
    """轴向响应曲线配置"""
    wavelengths: List[float]  # 波长列表 [nm]
    focal_offsets: List[float]  # 各波长焦点偏移 [μm]
    na: float  # 数值孔径
  

@dataclass
class DifferentialResult:
    """差动计算结果"""
    height_map: np.ndarray  # 高度图 [μm]
    confidence_map: np.ndarray  # 置信度图
    intensity_sum: np.ndarray  # 光强和图像


class AlgoService:
    """算法服务
  
    提供DAC-3D的核心算法:
    1. 差动信号计算
    2. ARC标定
    3. 3D点云重建
    4. CFAN自动聚焦推理
    """
  
    def __init__(self, arc_config: ARCConfig, use_gpu: bool = True):
        self._arc_config = arc_config
        self._use_gpu = use_gpu and HAS_CUDA
  
        if self._use_gpu:
            print("算法服务: 使用GPU加速")
            self._xp = cp
        else:
            print("算法服务: 使用CPU计算")
            self._xp = np
  
        # ARC查找表 (预计算)
        self._arc_lut: Optional[np.ndarray] = None
        self._build_arc_lut()
  
        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=4)
  
        # CFAN模型 (延迟加载)
        self._cfan_model = None
  
    def compute_differential(
        self,
        img_short: np.ndarray,
        img_long: np.ndarray
    ) -> DifferentialResult:
        """计算差动信号
  
        差动公式: D = (I1 - I2) / (I1 + I2)
  
        Args:
            img_short: 短波长图像
            img_long: 长波长图像
      
        Returns:
            差动计算结果
        """
        xp = self._xp
  
        # 转移到GPU（如果使用）
        if self._use_gpu:
            img_short = cp.asarray(img_short, dtype=cp.float32)
            img_long = cp.asarray(img_long, dtype=cp.float32)
        else:
            img_short = img_short.astype(np.float32)
            img_long = img_long.astype(np.float32)
  
        # 计算差动信号
        intensity_sum = img_short + img_long
        intensity_diff = img_short - img_long
  
        # 避免除零
        epsilon = 1e-6
        differential = intensity_diff / (intensity_sum + epsilon)
  
        # 通过ARC查找表转换为高度
        height_map = self._differential_to_height(differential)
  
        # 计算置信度（基于光强和）
        confidence = intensity_sum / intensity_sum.max()
  
        # 转回CPU
        if self._use_gpu:
            height_map = cp.asnumpy(height_map)
            confidence = cp.asnumpy(confidence)
            intensity_sum = cp.asnumpy(intensity_sum)
  
        return DifferentialResult(
            height_map=height_map,
            confidence_map=confidence,
            intensity_sum=intensity_sum
        )
  
    def compute_multi_wavelength(
        self,
        images: List[np.ndarray]
    ) -> np.ndarray:
        """多波长融合计算
  
        使用多对波长的差动信号，扩展轴向测量范围
  
        Args:
            images: 多波长图像列表 [img_λ1, img_λ2, img_λ3, ...]
      
        Returns:
            融合后的高度图
        """
        if len(images) < 2:
            raise ValueError("至少需要2个波长的图像")
  
        n_wavelengths = len(images)
        height, width = images[0].shape[:2]
  
        # 计算所有相邻波长对的差动
        differentials = []
        for i in range(n_wavelengths - 1):
            result = self.compute_differential(images[i], images[i + 1])
            differentials.append(result.height_map)
  
        # 加权融合（置信度加权）
        weights = []
        for i in range(len(differentials)):
            # 基于差动信号斜率计算权重
            weight = self._compute_arc_weight(i)
            weights.append(weight)
  
        weights = np.array(weights)
        weights = weights / weights.sum()
  
        # 融合
        height_map = np.zeros((height, width), dtype=np.float32)
        for i, h in enumerate(differentials):
            height_map += weights[i] * h
  
        return height_map
  
    def calibrate_arc(
        self,
        z_positions: np.ndarray,
        intensities: List[np.ndarray]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """标定轴向响应曲线 (ARC)
  
        Args:
            z_positions: Z轴位置序列 [μm]
            intensities: 各Z位置的光强图像序列
      
        Returns:
            (arc_curve, arc_derivative): ARC曲线和导数
        """
        n_points = len(z_positions)
  
        # 计算每个位置的平均光强
        mean_intensities = [np.mean(img) for img in intensities]
        mean_intensities = np.array(mean_intensities)
  
        # 归一化
        arc_curve = mean_intensities / mean_intensities.max()
  
        # 计算导数（用于灵敏度分析）
        arc_derivative = np.gradient(arc_curve, z_positions)
  
        return arc_curve, arc_derivative
  
    def predict_focus_cfan(
        self,
        images: List[np.ndarray]
    ) -> float:
        """使用CFAN模型预测离焦距离
  
        Args:
            images: 三相机图像 [img_top, img_center, img_bottom]
      
        Returns:
            预测的离焦距离 [μm]
        """
        if self._cfan_model is None:
            self._load_cfan_model()
  
        # 预处理
        input_tensor = self._preprocess_for_cfan(images)
  
        # 推理
        with torch.no_grad():
            output = self._cfan_model(input_tensor)
  
        defocus_um = output.item()
        return defocus_um
  
    def _build_arc_lut(self):
        """构建ARC查找表"""
        # 差动值范围: [-1, 1]
        # 对应高度范围: 取决于色散量
  
        differential_range = np.linspace(-1, 1, 10001)
  
        # 简化的ARC模型（实际应从标定数据拟合）
        # 差动值与高度的关系近似线性（在小范围内）
        dispersion_range = self._arc_config.focal_offsets[-1] - self._arc_config.focal_offsets[0]
  
        self._arc_lut = differential_range * (dispersion_range / 2)
  
    def _differential_to_height(self, differential: np.ndarray) -> np.ndarray:
        """差动值转高度
  
        使用预计算的查找表进行快速转换
        """
        xp = self._xp
  
        # 限制差动值范围
        differential = xp.clip(differential, -1, 1)
  
        # 查找表索引
        indices = ((differential + 1) / 2 * 10000).astype(int)
        indices = xp.clip(indices, 0, 10000)
  
        # 查表
        if self._use_gpu:
            lut = cp.asarray(self._arc_lut)
            height = lut[indices]
        else:
            height = self._arc_lut[indices]
  
        return height
  
    def _compute_arc_weight(self, pair_index: int) -> float:
        """计算ARC权重"""
        # 基于波长对的灵敏度分配权重
        # 短波长对在小范围内灵敏度高
        # 长波长对测量范围大
        # 这里简化为均匀权重
        return 1.0
  
    def _load_cfan_model(self):
        """加载CFAN模型"""
        import torch
        from ..algorithms.cfan_model import CFAN
  
        self._cfan_model = CFAN()
  
        # 加载预训练权重
        model_path = "models/cfan_weights.pth"
        try:
            state_dict = torch.load(model_path, map_location='cuda' if self._use_gpu else 'cpu')
            self._cfan_model.load_state_dict(state_dict)
            self._cfan_model.eval()
      
            if self._use_gpu:
                self._cfan_model.cuda()
        except FileNotFoundError:
            print(f"警告: CFAN模型文件不存在: {model_path}")
  
    def _preprocess_for_cfan(self, images: List[np.ndarray]) -> 'torch.Tensor':
        """CFAN输入预处理"""
        import torch
  
        # 调整大小
        resized = [cv2.resize(img, (256, 256)) for img in images]
  
        # 归一化
        normalized = [img.astype(np.float32) / 255.0 for img in resized]
  
        # 堆叠
        stacked = np.stack(normalized, axis=0)  # [3, H, W]
  
        # 转Tensor
        tensor = torch.from_numpy(stacked).unsqueeze(0)  # [1, 3, H, W]
  
        if self._use_gpu:
            tensor = tensor.cuda()
  
        return tensor
```

---

### 四、FPGA Verilog核心模块

```verilog
// fpga/vivado/src/timing_ctrl.v
// 时序控制器顶层模块

module timing_ctrl #(
    parameter CLK_FREQ = 100_000_000,  // 100MHz系统时钟
    parameter ENC_BITS = 32            // 编码器位数
)(
    input  wire        clk,
    input  wire        rst_n,
  
    // AXI-Lite接口 (简化版)
    input  wire [5:0]  axi_addr,
    input  wire [31:0] axi_wdata,
    input  wire        axi_wen,
    output reg  [31:0] axi_rdata,
  
    // 编码器输入 (差分)
    input  wire        enc_a_p, enc_a_n,
    input  wire        enc_b_p, enc_b_n,
  
    // 触发输出
    output wire        trig_cam,    // 相机触发
    output wire        trig_dmd,    // DMD触发
    output wire        trig_led,    // LED触发/PWM
  
    // 状态输出
    output wire [31:0] frame_cnt,
    output wire [31:0] timestamp
);

    // ========== 寄存器定义 ==========
    reg [31:0] reg_ctrl;        // 0x00
    reg [31:0] reg_pso_start;   // 0x08
    reg [31:0] reg_pso_end;     // 0x0C
    reg [31:0] reg_pso_interval;// 0x10
    reg [31:0] reg_pwm_period;  // 0x18
    reg [31:0] reg_pwm_duty0;   // 0x1C
    reg [31:0] reg_pwm_duty1;   // 0x20
    reg [31:0] reg_pwm_duty2;   // 0x24
    reg [31:0] reg_trig_delay;  // 0x3C
  
    // 状态寄存器 (只读)
    wire [31:0] reg_status;
    wire [31:0] reg_enc_pos;
  
    // ========== 编码器解码 ==========
    wire enc_a, enc_b;
    wire signed [ENC_BITS-1:0] encoder_count;
  
    // 差分转单端
    IBUFDS ibuf_a (.I(enc_a_p), .IB(enc_a_n), .O(enc_a));
    IBUFDS ibuf_b (.I(enc_b_p), .IB(enc_b_n), .O(enc_b));
  
    encoder_decoder #(
        .BITS(ENC_BITS)
    ) enc_dec (
        .clk(clk),
        .rst_n(rst_n),
        .enc_a(enc_a),
        .enc_b(enc_b),
        .count(encoder_count)
    );
  
    assign reg_enc_pos = encoder_count;
  
    // ========== PSO触发生成 ==========
    wire pso_enable = reg_ctrl[0];
    wire pso_armed  = reg_ctrl[2];
  
    wire pso_trigger;
    reg [31:0] pso_frame_count;
  
    pso_generator #(
        .BITS(ENC_BITS)
    ) pso_gen (
        .clk(clk),
        .rst_n(rst_n),
        .enable(pso_enable),
        .armed(pso_armed),
        .position(encoder_count),
        .start_pos(reg_pso_start),
        .end_pos(reg_pso_end),
        .interval(reg_pso_interval),
        .trigger(pso_trigger),
        .frame_count(pso_frame_count)
    );
  
    assign frame_cnt = pso_frame_count;
  
    // ========== 触发延迟与脉冲整形 ==========
    wire trig_delayed;
  
    delay_line #(
        .MAX_DELAY(1000)  // 最大10μs延迟
    ) trig_delay (
        .clk(clk),
        .rst_n(rst_n),
        .delay_ticks(reg_trig_delay[9:0]),
        .in(pso_trigger),
        .out(trig_delayed)
    );
  
    // 脉冲整形 (生成固定宽度脉冲)
    pulse_shaper cam_pulse (
        .clk(clk),
        .rst_n(rst_n),
        .trigger(trig_delayed),
        .width(reg_pwm_duty0[15:0]),
        .pulse(trig_cam)
    );
  
    pulse_shaper dmd_pulse (
        .clk(clk),
        .rst_n(rst_n),
        .trigger(trig_delayed),
        .width(reg_pwm_duty1[15:0]),
        .pulse(trig_dmd)
    );
  
    // ========== LED PWM控制 ==========
    pwm_controller led_pwm (
        .clk(clk),
        .rst_n(rst_n),
        .period(reg_pwm_period),
        .duty(reg_pwm_duty2),
        .pwm_out(trig_led)
    );
  
    // ========== 时间戳计数器 ==========
    reg [31:0] ts_counter;
    reg [6:0]  us_divider;
  
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ts_counter <= 0;
            us_divider <= 0;
        end else begin
            if (us_divider == CLK_FREQ/1_000_000 - 1) begin
                us_divider <= 0;
                ts_counter <= ts_counter + 1;
            end else begin
                us_divider <= us_divider + 1;
            end
        end
    end
  
    assign timestamp = ts_counter;
  
    // ========== 状态机 ==========
    localparam ST_IDLE     = 4'd0;
    localparam ST_ARMED    = 4'd1;
    localparam ST_SCANNING = 4'd2;
    localparam ST_COMPLETE = 4'd3;
    localparam ST_ERROR    = 4'd4;
  
    reg [3:0] state;
  
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= ST_IDLE;
        end else begin
            case (state)
                ST_IDLE: begin
                    if (reg_ctrl[2])  // ARM bit
                        state <= ST_ARMED;
                end
                ST_ARMED: begin
                    if (reg_ctrl[0])  // ENABLE bit
                        state <= ST_SCANNING;
                    else if (!reg_ctrl[2])
                        state <= ST_IDLE;
                end
                ST_SCANNING: begin
                    if (!reg_ctrl[0])
                        state <= ST_COMPLETE;
                    else if (encoder_count >= $signed(reg_pso_end))
                        state <= ST_COMPLETE;
                end
                ST_COMPLETE: begin
                    if (reg_ctrl[1])  // RESET bit
                        state <= ST_IDLE;
                end
                ST_ERROR: begin
                    if (reg_ctrl[1])
                        state <= ST_IDLE;
                end
                default: state <= ST_IDLE;
            endcase
        end
    end
  
    // 状态寄存器
    assign reg_status = {pso_frame_count[15:0], 4'b0, state, 
                         2'b0, (state == ST_ARMED), (state != ST_IDLE)};
  
    // ========== AXI寄存器读写 ==========
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_ctrl <= 0;
            reg_pso_start <= 0;
            reg_pso_end <= 32'h7FFFFFFF;
            reg_pso_interval <= 100;
            reg_pwm_period <= 10000;
            reg_pwm_duty0 <= 100;
            reg_pwm_duty1 <= 100;
            reg_pwm_duty2 <= 5000;
            reg_trig_delay <= 0;
        end else if (axi_wen) begin
            case (axi_addr)
                6'h00: reg_ctrl <= axi_wdata;
                6'h08: reg_pso_start <= axi_wdata;
                6'h0C: reg_pso_end <= axi_wdata;
                6'h10: reg_pso_interval <= axi_wdata;
                6'h18: reg_pwm_period <= axi_wdata;
                6'h1C: reg_pwm_duty0 <= axi_wdata;
                6'h20: reg_pwm_duty1 <= axi_wdata;
                6'h24: reg_pwm_duty2 <= axi_wdata;
                6'h3C: reg_trig_delay <= axi_wdata;
            endcase
        end
    end
  
    // 读取
    always @(*) begin
        case (axi_addr)
            6'h00: axi_rdata = reg_ctrl;
            6'h04: axi_rdata = reg_status;
            6'h08: axi_rdata = reg_pso_start;
            6'h0C: axi_rdata = reg_pso_end;
            6'h10: axi_rdata = reg_pso_interval;
            6'h18: axi_rdata = reg_pwm_period;
            6'h1C: axi_rdata = reg_pwm_duty0;
            6'h20: axi_rdata = reg_pwm_duty1;
            6'h24: axi_rdata = reg_pwm_duty2;
            6'h28: axi_rdata = reg_enc_pos;
            6'h34: axi_rdata = pso_frame_count;
            6'h38: axi_rdata = ts_counter;
            6'h3C: axi_rdata = reg_trig_delay;
            default: axi_rdata = 32'hDEADBEEF;
        endcase
    end

endmodule
```

```verilog
// fpga/vivado/src/pso_generator.v
// 位置同步输出生成器

module pso_generator #(
    parameter BITS = 32
)(
    input  wire                    clk,
    input  wire                    rst_n,
    input  wire                    enable,
    input  wire                    armed,
    input  wire signed [BITS-1:0]  position,
    input  wire signed [BITS-1:0]  start_pos,
    input  wire signed [BITS-1:0]  end_pos,
    input  wire        [BITS-1:0]  interval,
    output reg                     trigger,
    output reg         [31:0]      frame_count
);

    reg signed [BITS-1:0] next_trigger_pos;
    reg in_range;
    reg prev_in_range;
  
    // 判断是否在扫描范围内
    always @(*) begin
        in_range = (position >= start_pos) && (position <= end_pos);
    end
  
    // 主逻辑
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            trigger <= 0;
            frame_count <= 0;
            next_trigger_pos <= 0;
            prev_in_range <= 0;
        end else begin
            prev_in_range <= in_range;
            trigger <= 0;  // 默认不触发
      
            if (!enable) begin
                // 禁用时复位
                frame_count <= 0;
                next_trigger_pos <= start_pos;
            end else if (armed && !prev_in_range && in_range) begin
                // 刚进入范围，初始化
                next_trigger_pos <= start_pos;
                frame_count <= 0;
            end else if (enable && in_range) begin
                // 在范围内，检查是否到达触发点
                if (position >= next_trigger_pos) begin
                    trigger <= 1;
                    frame_count <= frame_count + 1;
                    next_trigger_pos <= next_trigger_pos + $signed(interval);
                end
            end
        end
    end

endmodule
```

```verilog
// fpga/vivado/src/encoder_decoder.v
// 正交编码器解码器 (4倍频)

module encoder_decoder #(
    parameter BITS = 32
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   enc_a,
    input  wire                   enc_b,
    output reg signed [BITS-1:0]  count
);

    // 输入同步和消抖
    reg [2:0] a_sync, b_sync;
  
    always @(posedge clk) begin
        a_sync <= {a_sync[1:0], enc_a};
        b_sync <= {b_sync[1:0], enc_b};
    end
  
    wire a_clean = a_sync[2];
    wire b_clean = b_sync[2];
  
    // 边沿检测
    reg a_prev, b_prev;
    wire a_rise = a_clean && !a_prev;
    wire a_fall = !a_clean && a_prev;
    wire b_rise = b_clean && !b_prev;
    wire b_fall = !b_clean && b_prev;
  
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a_prev <= 0;
            b_prev <= 0;
            count <= 0;
        end else begin
            a_prev <= a_clean;
            b_prev <= b_clean;
      
            // 4倍频解码
            case ({a_rise, a_fall, b_rise, b_fall})
                4'b1000: count <= count + (b_clean ? -1 : 1);
                4'b0100: count <= count + (b_clean ? 1 : -1);
                4'b0010: count <= count + (a_clean ? 1 : -1);
                4'b0001: count <= count + (a_clean ? -1 : 1);
                default: ;  // 无变化或非法状态
            endcase
        end
    end

endmodule
```

---

### 五、配置文件示例

```yaml
# configs/devices.yaml
# 设备配置文件

fpga:
  type: zynq
  ip_address: "192.168.1.100"
  port: 5000
  timeout_s: 5.0
  encoder_resolution: 1.0  # μm/count

stage:
  xy:
    type: zmotion
    card_ip: "192.168.0.11"
    x_axis: 0
    y_axis: 1
    velocity: 10000  # μm/s
    acceleration: 50000  # μm/s²
  z:
    type: pi_piezo
    controller: "E-709"
    serial_port: "COM3"
    range: 100  # μm

cameras:
  - id: "cam_top"
    type: basler
    serial: "12345678"
    ip: "192.168.2.10"
    exposure_us: 1000
    gain_db: 0
  - id: "cam_center"  
    type: basler
    serial: "12345679"
    ip: "192.168.2.11"
    exposure_us: 1000
    gain_db: 0
  - id: "cam_bottom"
    type: basler
    serial: "12345680"
    ip: "192.168.2.12"
    exposure_us: 1000
    gain_db: 0

dmd:
  type: dlp6500
  resolution: [1920, 1080]
  pattern_rate: 1000  # Hz

light:
  type: rgb_led
  channels: 3
  max_current_ma: 1000

arc:
  wavelengths: [460, 525, 620]  # nm
  focal_offsets: [-50, 0, 50]   # μm
  na: 0.25
```

```yaml
# configs/recipes/wedge_filter.yaml
# 楔形滤光片检测配方

name: "楔形滤光片表面瑕疵检测"
version: "1.0"

scan:
  type: fly_scan
  region:
    start: {x: 0, y: 0}
    end: {x: 25000, y: 25000}
    step_x: 10
    step_y: 500
  velocity: 5000  # μm/s

imaging:
  exposure_us: 500
  gain_db: 6
  n_averages: 1
  
autofocus:
  enabled: true
  method: cfan
  tolerance_um: 20
  
defect_detection:
  enabled: true
  model: "models/defect_yolov8.pt"
  confidence_threshold: 0.5
  classes: ["scratch", "pit", "contamination"]
  
output:
  save_raw: false
  save_3d: true
  format: hdf5
  path: "data/inspections/"
```

---

### 六、开发路线图

| 阶段              | 周期      | 目标     | 交付物                           | 负责人      |
| ----------------- | --------- | -------- | -------------------------------- | ----------- |
| **Phase 0** | 第1-2周   | 环境搭建 | 开发环境、Git仓库、CI/CD         | 全员        |
| **Phase 1** | 第3-6周   | FPGA基础 | Vivado工程、时序控制器、仿真通过 | FPGA工程师  |
| **Phase 2** | 第5-8周   | HAL层    | 所有设备驱动、模拟器、单元测试   | 软件工程师A |
| **Phase 3** | 第7-10周  | 核心服务 | 扫描服务、算法服务、集成测试     | 软件工程师B |
| **Phase 4** | 第9-12周  | 系统联调 | FPGA+软件联调、飞拍验证          | 全员        |
| **Phase 5** | 第11-14周 | UI开发   | PyQt界面、Napari插件             | UI工程师    |
| **Phase 6** | 第13-16周 | 算法集成 | CFAN部署、ARC标定、点云重建      | 算法工程师  |
| **Phase 7** | 第15-20周 | 产线验证 | 大鱼视觉/希恩凯现场测试          | 项目负责人  |
| **Phase 8** | 第19-24周 | 优化迭代 | 稳定性提升、文档完善、培训       | 全员        |

---

这份架构设计覆盖了从FPGA到上位机的完整链路，核心要点：

1. **FPGA自主触发**：Python只负责配置和监督，纳秒级时序由硬件保证
2. **严格分层**：接口定义清晰，换设备只改驱动层
3. **可测试性**：每层都有模拟器，可以在没有硬件的情况下开发
4. **扩展性**：瞬态检测只需要升级FPGA逻辑和添加高速采集卡驱动

需要我进一步细化某个模块吗？
