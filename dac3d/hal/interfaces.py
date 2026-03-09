"""
硬件抽象层接口定义
所有硬件驱动必须实现这些接口，确保可替换性和可测试性

设计原则:
1. 接口定义与实现分离
2. 所有方法返回明确的状态
3. 支持异步操作
4. 错误处理统一
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, List, Tuple, Dict, Any
import numpy as np
from numpy.typing import NDArray


# ============== 数据结构 ==============

@dataclass
class Position:
    """三维位置坐标"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    def to_tuple(self) -> Tuple[float, float, float]:
        """转换为元组"""
        return (self.x, self.y, self.z)
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {"x": self.x, "y": self.y, "z": self.z}
    
    def __repr__(self) -> str:
        return f"Position(x={self.x:.3f}, y={self.y:.3f}, z={self.z:.3f})"


@dataclass
class ScanRegion:
    """扫描区域定义"""
    start: Position
    end: Position
    step_x: float
    step_y: float
    step_z: float = 0.0  # Z方向步进（用于多层扫描）
    
    @property
    def n_points_x(self) -> int:
        """X方向点数"""
        return int(abs(self.end.x - self.start.x) / self.step_x) + 1
    
    @property
    def n_points_y(self) -> int:
        """Y方向点数"""
        return int(abs(self.end.y - self.start.y) / self.step_y) + 1
    
    @property
    def total_points(self) -> int:
        """总点数"""
        return self.n_points_x * self.n_points_y


@dataclass
class TriggerConfig:
    """触发配置参数"""
    mode: str = 'position'  # 'position', 'time', 'software'
    start_pos: float = 0.0  # 起始位置(μm)
    end_pos: float = 1000.0  # 结束位置(μm)
    interval: float = 10.0  # 触发间隔: 位置(μm)或时间(μs)
    pulse_width_ns: int = 1000  # 触发脉冲宽度(ns)
    delay_ns: int = 0  # 触发延迟补偿(ns)
    axis: str = 'x'  # 监控轴: 'x', 'y', 'z'
    
    def validate(self) -> bool:
        """验证配置有效性"""
        if self.mode not in ['position', 'time', 'software']:
            return False
        if self.interval <= 0:
            return False
        if self.pulse_width_ns < 100 or self.pulse_width_ns > 1000000:
            return False
        return True


@dataclass
class CameraConfig:
    """相机配置参数"""
    exposure_us: float = 1000.0  # 曝光时间(微秒)
    gain: float = 0.0  # 增益(dB)
    roi: Optional[Tuple[int, int, int, int]] = None  # ROI (x, y, width, height)
    pixel_format: str = "Mono12"  # 像素格式
    trigger_mode: str = "hardware"  # 触发模式
    trigger_source: str = "Line1"  # 触发源
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "exposure_us": self.exposure_us,
            "gain": self.gain,
            "roi": self.roi,
            "pixel_format": self.pixel_format,
            "trigger_mode": self.trigger_mode,
            "trigger_source": self.trigger_source,
        }


class DeviceState(Enum):
    """设备状态枚举"""
    DISCONNECTED = auto()  # 未连接
    CONNECTED = auto()  # 已连接
    IDLE = auto()  # 空闲
    READY = auto()  # 就绪
    BUSY = auto()  # 忙碌
    ERROR = auto()  # 错误
    HOMING = auto()  # 回零中
    MOVING = auto()  # 运动中
    ACQUIRING = auto()  # 采集中


class TriggerMode(Enum):
    """触发模式"""
    SOFTWARE = "software"  # 软件触发
    HARDWARE = "hardware"  # 硬件触发
    CONTINUOUS = "continuous"  # 连续采集
    FREERUN = "freerun"  # 自由运行


# ============== 抽象接口 ==============

class IDevice(ABC):
    """所有设备的基类接口"""
    
    def __init__(self, device_id: str, config: Optional[Dict[str, Any]] = None):
        self._device_id = device_id
        self._config = config or {}
        self._state = DeviceState.DISCONNECTED
        self._error_msg = ""
    
    @property
    def device_id(self) -> str:
        """设备ID"""
        return self._device_id
    
    @property
    def state(self) -> DeviceState:
        """获取设备状态"""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._state != DeviceState.DISCONNECTED
    
    @property
    def error_message(self) -> str:
        """错误消息"""
        return self._error_msg
    
    @abstractmethod
    def connect(self) -> bool:
        """连接设备
        
        Returns:
            bool: 成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """断开设备连接"""
        pass
    
    @abstractmethod
    def reset(self) -> bool:
        """复位设备"""
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """获取设备信息
        
        Returns:
            Dict: 包含设备型号、序列号、版本等信息
        """
        pass


class IStage(IDevice):
    """运动台抽象接口
    
    适用于XY平台和Z轴压电台
    """
    
    @abstractmethod
    def home(self, axes: Optional[List[str]] = None) -> bool:
        """回零操作
        
        Args:
            axes: 需要回零的轴列表，None表示所有轴
            
        Returns:
            bool: 成功返回True
        """
        pass
    
    @abstractmethod
    def move_to(self, pos: Position, wait: bool = True, velocity: Optional[float] = None) -> bool:
        """移动到指定位置(绝对移动)
        
        Args:
            pos: 目标位置
            wait: 是否等待运动完成
            velocity: 运动速度(可选，使用默认速度如果为None)
            
        Returns:
            bool: 命令发送成功返回True
        """
        pass
    
    @abstractmethod
    def move_relative(self, delta: Position, wait: bool = True) -> bool:
        """相对移动
        
        Args:
            delta: 相对位移
            wait: 是否等待运动完成
            
        Returns:
            bool: 成功返回True
        """
        pass
    
    @abstractmethod
    def stop(self, emergency: bool = False) -> bool:
        """停止运动
        
        Args:
            emergency: 是否紧急停止(立即停止，可能丢失位置)
            
        Returns:
            bool: 成功返回True
        """
        pass
    
    @abstractmethod
    def get_position(self) -> Position:
        """获取当前位置"""
        pass
    
    @abstractmethod
    def set_velocity(self, velocity: float, axis: Optional[str] = None) -> bool:
        """设置运动速度
        
        Args:
            velocity: 速度值(单位: μm/s)
            axis: 指定轴，None表示所有轴
        """
        pass
    
    @abstractmethod
    def set_acceleration(self, accel: float, axis: Optional[str] = None) -> bool:
        """设置加速度
        
        Args:
            accel: 加速度值(单位: μm/s²)
            axis: 指定轴
        """
        pass
    
    @property
    @abstractmethod
    def is_moving(self) -> bool:
        """是否正在运动"""
        pass
    
    @property
    @abstractmethod
    def is_homed(self) -> bool:
        """是否已回零"""
        pass


class ICamera(IDevice):
    """相机抽象接口"""
    
    @abstractmethod
    def set_exposure(self, exposure_us: float) -> bool:
        """设置曝光时间
        
        Args:
            exposure_us: 曝光时间(微秒)
        """
        pass
    
    @abstractmethod
    def set_gain(self, gain: float) -> bool:
        """设置增益
        
        Args:
            gain: 增益值(dB)
        """
        pass
    
    @abstractmethod
    def set_roi(self, x: int, y: int, width: int, height: int) -> bool:
        """设置感兴趣区域
        
        Args:
            x, y: ROI左上角坐标
            width, height: ROI宽高
        """
        pass
    
    @abstractmethod
    def set_trigger_mode(self, mode: TriggerMode, source: str = "Line1") -> bool:
        """设置触发模式
        
        Args:
            mode: 触发模式
            source: 触发源(如"Line1", "Line2")
        """
        pass
    
    @abstractmethod
    def start_acquisition(self) -> bool:
        """开始采集(进入等待触发状态)"""
        pass
    
    @abstractmethod
    def stop_acquisition(self) -> bool:
        """停止采集"""
        pass
    
    @abstractmethod
    def grab(self, timeout_ms: int = 5000) -> Optional[NDArray[np.uint16]]:
        """抓取一帧图像
        
        Args:
            timeout_ms: 超时时间(毫秒)
            
        Returns:
            NDArray: 图像数据，失败返回None
        """
        pass
    
    @abstractmethod
    def grab_sequence(self, n_frames: int, timeout_ms: int = 30000) -> List[NDArray[np.uint16]]:
        """抓取序列图像
        
        Args:
            n_frames: 帧数
            timeout_ms: 总超时时间
            
        Returns:
            List[NDArray]: 图像序列
        """
        pass
    
    @abstractmethod
    def get_frame_count(self) -> int:
        """获取已采集帧数"""
        pass
    
    @property
    @abstractmethod
    def width(self) -> int:
        """图像宽度"""
        pass
    
    @property
    @abstractmethod
    def height(self) -> int:
        """图像高度"""
        pass


class IDMD(IDevice):
    """DMD(数字微镜)抽象接口"""
    
    @abstractmethod
    def load_pattern(self, pattern: NDArray[np.uint8]) -> bool:
        """加载图样
        
        Args:
            pattern: 二值图样，shape=(height, width)
        """
        pass
    
    @abstractmethod
    def load_pattern_sequence(self, patterns: List[NDArray[np.uint8]]) -> bool:
        """加载图样序列
        
        Args:
            patterns: 图样列表
        """
        pass
    
    @abstractmethod
    def display_pattern(self, index: int = 0) -> bool:
        """显示指定图样
        
        Args:
            index: 图样索引
        """
        pass
    
    @abstractmethod
    def start_sequence(self, trigger_mode: TriggerMode = TriggerMode.SOFTWARE) -> bool:
        """启动序列显示
        
        Args:
            trigger_mode: 触发模式
        """
        pass
    
    @abstractmethod
    def stop_sequence(self) -> bool:
        """停止序列显示"""
        pass
    
    @abstractmethod
    def set_illumination(self, intensity: float) -> bool:
        """设置亮度
        
        Args:
            intensity: 亮度 (0.0-1.0)
        """
        pass


class ILight(IDevice):
    """光源抽象接口"""
    
    @abstractmethod
    def set_intensity(self, intensity: float, channel: Optional[int] = None) -> bool:
        """设置光强
        
        Args:
            intensity: 光强 (0.0-1.0)
            channel: 通道号，None表示所有通道
        """
        pass
    
    @abstractmethod
    def set_rgb(self, r: float, g: float, b: float) -> bool:
        """设置RGB值
        
        Args:
            r, g, b: RGB值 (0.0-1.0)
        """
        pass
    
    @abstractmethod
    def turn_on(self, channel: Optional[int] = None) -> bool:
        """打开光源"""
        pass
    
    @abstractmethod
    def turn_off(self, channel: Optional[int] = None) -> bool:
        """关闭光源"""
        pass
    
    @abstractmethod
    def set_trigger_mode(self, mode: TriggerMode) -> bool:
        """设置触发模式"""
        pass


class IFPGA(IDevice):
    """FPGA控制器抽象接口
    
    用于Zynq等FPGA+ARM SoC，负责硬件实时触发控制
    """
    
    @abstractmethod
    def write_register(self, addr: int, value: int) -> bool:
        """写寄存器
        
        Args:
            addr: 寄存器地址
            value: 写入值
        """
        pass
    
    @abstractmethod
    def read_register(self, addr: int) -> int:
        """读寄存器
        
        Args:
            addr: 寄存器地址
            
        Returns:
            int: 寄存器值
        """
        pass
    
    @abstractmethod
    def configure_pso(self, config: TriggerConfig) -> bool:
        """配置位置同步输出(PSO)
        
        Args:
            config: 触发配置
        """
        pass
    
    @abstractmethod
    def start_pso(self) -> bool:
        """启动PSO触发"""
        pass
    
    @abstractmethod
    def stop_pso(self) -> bool:
        """停止PSO触发"""
        pass
    
    @abstractmethod
    def get_encoder_position(self, axis: str) -> float:
        """获取编码器位置
        
        Args:
            axis: 'x', 'y', 'z'
        """
        pass
    
    @abstractmethod
    def get_frame_count(self) -> int:
        """获取触发帧计数"""
        pass
    
    @abstractmethod
    def get_timestamp(self) -> int:
        """获取时间戳(微秒)"""
        pass
    
    @abstractmethod
    def set_pwm(self, channel: int, period_ns: int, duty: float) -> bool:
        """设置PWM输出
        
        Args:
            channel: 通道号(0-3)
            period_ns: 周期(纳秒)
            duty: 占空比(0.0-1.0)
        """
        pass


# ============== 回调类型定义 ==============

PositionCallback = Callable[[Position], None]
StateCallback = Callable[[DeviceState], None]
ErrorCallback = Callable[[str], None]
ImageCallback = Callable[[NDArray], None]


__all__ = [
    # 数据结构
    "Position",
    "ScanRegion",
    "TriggerConfig",
    "CameraConfig",
    # 枚举
    "DeviceState",
    "TriggerMode",
    # 接口
    "IDevice",
    "IStage",
    "ICamera",
    "IDMD",
    "ILight",
    "IFPGA",
    # 回调类型
    "PositionCallback",
    "StateCallback",
    "ErrorCallback",
    "ImageCallback",
]
