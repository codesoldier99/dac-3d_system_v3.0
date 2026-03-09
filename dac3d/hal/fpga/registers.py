"""
FPGA寄存器映射定义

与FPGA Verilog代码中的寄存器地址保持一致
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, Any


class RegisterAddress(IntEnum):
    """寄存器地址映射"""
    # 控制寄存器
    CTRL = 0x00  # [0]:全局使能 [1]:软复位 [2]:PSO使能 [3]:预留
    STATUS = 0x04  # [0]:忙 [1]:错误 [7:4]:状态 [31:16]:帧计数
    
    # PSO(位置同步输出)配置
    PSO_START = 0x08  # PSO触发起始位置(编码器计数)
    PSO_END = 0x0C  # PSO触发结束位置
    PSO_INTERVAL = 0x10  # PSO触发间隔
    PSO_MODE = 0x14  # [1:0]:模式 0=单次 1=连续 2=往返
    
    # PWM控制
    PWM_PERIOD = 0x18  # PWM周期(单位:10ns)
    PWM_DUTY_0 = 0x1C  # 通道0占空比(相机)
    PWM_DUTY_1 = 0x20  # 通道1占空比(DMD)
    PWM_DUTY_2 = 0x24  # 通道2占空比(LED)
    PWM_DUTY_3 = 0x28  # 通道3占空比(预留)
    
    # 编码器读取
    ENC_X_POS = 0x2C  # X轴编码器位置
    ENC_Y_POS = 0x30  # Y轴编码器位置
    ENC_Z_POS = 0x34  # Z轴位置(可能是模拟量)
    
    # 计数器和时间戳
    FRAME_CNT = 0x38  # 帧计数器
    TIMESTAMP = 0x3C  # 时间戳(μs)
    
    # 高级配置
    TRIG_DELAY = 0x40  # 触发延迟补偿(单位:10ns)
    TRIG_WIDTH = 0x44  # 触发脉冲宽度(单位:10ns)
    
    # 调试寄存器
    DEBUG_0 = 0xF0
    DEBUG_1 = 0xF4
    VERSION = 0xFC  # FPGA版本号


class ControlBits:
    """控制寄存器位定义"""
    GLOBAL_EN = 0  # 全局使能
    SOFT_RESET = 1  # 软复位
    PSO_EN = 2  # PSO使能
    ARM = 3  # ARM扫描


class StatusBits:
    """状态寄存器位定义"""
    BUSY = 0  # 忙碌
    ERROR = 1  # 错误
    PSO_ACTIVE = 2  # PSO激活
    STATE_SHIFT = 4  # 状态字段起始位
    STATE_MASK = 0xF  # 状态掩码(4位)
    FRAME_CNT_SHIFT = 16  # 帧计数起始位
    FRAME_CNT_MASK = 0xFFFF  # 帧计数掩码(16位)


class PSOMode(IntEnum):
    """PSO触发模式"""
    SINGLE = 0  # 单次扫描
    CONTINUOUS = 1  # 连续扫描
    BIDIRECTIONAL = 2  # 双向扫描(往返)


class FPGAState(IntEnum):
    """FPGA内部状态"""
    IDLE = 0
    ARMED = 1
    SCANNING = 2
    COMPLETE = 3
    ERROR = 15


@dataclass
class RegisterMap:
    """完整寄存器映射"""
    
    # 默认值
    DEFAULT_PWM_PERIOD = 10000  # 100kHz (单位10ns)
    DEFAULT_TRIG_WIDTH = 100  # 1μs
    DEFAULT_TRIG_DELAY = 0
    
    @staticmethod
    def make_ctrl_word(
        global_en: bool = False,
        soft_reset: bool = False,
        pso_en: bool = False,
        arm: bool = False
    ) -> int:
        """构造控制字
        
        Args:
            global_en: 全局使能
            soft_reset: 软复位
            pso_en: PSO使能
            arm: ARM扫描
            
        Returns:
            int: 32位控制字
        """
        ctrl = 0
        if global_en:
            ctrl |= (1 << ControlBits.GLOBAL_EN)
        if soft_reset:
            ctrl |= (1 << ControlBits.SOFT_RESET)
        if pso_en:
            ctrl |= (1 << ControlBits.PSO_EN)
        if arm:
            ctrl |= (1 << ControlBits.ARM)
        return ctrl
    
    @staticmethod
    def parse_status(status: int) -> Dict[str, Any]:
        """解析状态寄存器
        
        Args:
            status: 状态寄存器值
            
        Returns:
            Dict: 解析后的状态信息
        """
        return {
            "busy": bool(status & (1 << StatusBits.BUSY)),
            "error": bool(status & (1 << StatusBits.ERROR)),
            "pso_active": bool(status & (1 << StatusBits.PSO_ACTIVE)),
            "state": FPGAState((status >> StatusBits.STATE_SHIFT) & StatusBits.STATE_MASK),
            "frame_count": (status >> StatusBits.FRAME_CNT_SHIFT) & StatusBits.FRAME_CNT_MASK,
        }
    
    @staticmethod
    def encode_position_um_to_count(pos_um: float, encoder_resolution_nm: float = 1.0) -> int:
        """将位置(μm)转换为编码器计数
        
        Args:
            pos_um: 位置(微米)
            encoder_resolution_nm: 编码器分辨率(纳米)
            
        Returns:
            int: 编码器计数值
        """
        return int(pos_um * 1000.0 / encoder_resolution_nm)
    
    @staticmethod
    def decode_count_to_position_um(count: int, encoder_resolution_nm: float = 1.0) -> float:
        """将编码器计数转换为位置(μm)
        
        Args:
            count: 编码器计数
            encoder_resolution_nm: 编码器分辨率(纳米)
            
        Returns:
            float: 位置(微米)
        """
        return count * encoder_resolution_nm / 1000.0
    
    @staticmethod
    def ns_to_fpga_units(ns: int) -> int:
        """将纳秒转换为FPGA单位(10ns)
        
        Args:
            ns: 纳秒
            
        Returns:
            int: FPGA单位
        """
        return ns // 10
    
    @staticmethod
    def fpga_units_to_ns(units: int) -> int:
        """将FPGA单位转换为纳秒
        
        Args:
            units: FPGA单位
            
        Returns:
            int: 纳秒
        """
        return units * 10


class RegisterValidator:
    """寄存器值验证器"""
    
    @staticmethod
    def validate_pwm_period(period: int) -> bool:
        """验证PWM周期
        
        Args:
            period: 周期(FPGA单位)
            
        Returns:
            bool: 有效返回True
        """
        # 10kHz ~ 1MHz
        min_period = 100  # 1μs
        max_period = 10000  # 100μs
        return min_period <= period <= max_period
    
    @staticmethod
    def validate_pwm_duty(duty: float) -> bool:
        """验证占空比
        
        Args:
            duty: 占空比(0.0-1.0)
            
        Returns:
            bool: 有效返回True
        """
        return 0.0 <= duty <= 1.0
    
    @staticmethod
    def validate_position(pos: int) -> bool:
        """验证位置值
        
        Args:
            pos: 位置(编码器计数)
            
        Returns:
            bool: 有效返回True
        """
        # 假设32位有符号整数
        return -(2**31) <= pos < 2**31
    
    @staticmethod
    def validate_interval(interval: int) -> bool:
        """验证触发间隔
        
        Args:
            interval: 间隔(编码器计数)
            
        Returns:
            bool: 有效返回True
        """
        # 最小1μm, 最大10mm (假设1nm分辨率)
        min_interval = 1000  # 1μm
        max_interval = 10000000  # 10mm
        return min_interval <= interval <= max_interval


__all__ = [
    "RegisterAddress",
    "ControlBits",
    "StatusBits",
    "PSOMode",
    "FPGAState",
    "RegisterMap",
    "RegisterValidator",
]
