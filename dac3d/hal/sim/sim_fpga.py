"""
FPGA模拟驱动 - 软件在环仿真
"""

import logging
import time
from typing import Dict, Any
import numpy as np

from dac3d.hal.interfaces import IFPGA, DeviceState, TriggerConfig


logger = logging.getLogger(__name__)


class SimFPGA(IFPGA):
    """FPGA模拟器
    
    用于软件在环测试，模拟真实FPGA行为
    """
    
    def __init__(
        self,
        device_id: str = "sim_fpga",
        config: Dict[str, Any] = None
    ):
        super().__init__(device_id, config)
        
        # 模拟寄存器
        self._registers: Dict[int, int] = {}
        
        # PSO配置
        self._pso_config: TriggerConfig = None
        self._pso_running = False
        self._pso_position = 0.0
        
        # 编码器位置（模拟）
        self._enc_x = 0
        self._enc_y = 0
        self._enc_z = 0
        
        # 帧计数
        self._frame_count = 0
        self._timestamp = 0
        
        logger.info("SimFPGA initialized (Software-in-Loop mode)")
    
    def connect(self) -> bool:
        """模拟连接"""
        logger.info("SimFPGA: Simulated connection")
        time.sleep(0.1)  # 模拟连接延迟
        self._state = DeviceState.CONNECTED
        return True
    
    def disconnect(self) -> bool:
        """模拟断开"""
        logger.info("SimFPGA: Simulated disconnection")
        self._state = DeviceState.DISCONNECTED
        return True
    
    def reset(self) -> bool:
        """模拟复位"""
        logger.info("SimFPGA: Simulated reset")
        self._registers.clear()
        self._frame_count = 0
        self._timestamp = 0
        self._state = DeviceState.IDLE
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """获取设备信息"""
        return {
            "device_id": self._device_id,
            "type": "Simulated FPGA",
            "mode": "Software-in-Loop",
            "state": self._state.name,
            "frame_count": self._frame_count,
        }
    
    def write_register(self, addr: int, value: int) -> bool:
        """模拟写寄存器"""
        self._registers[addr] = value
        logger.debug(f"SimFPGA: Write reg[0x{addr:02X}] = 0x{value:08X}")
        return True
    
    def read_register(self, addr: int) -> int:
        """模拟读寄存器"""
        # 特殊处理动态寄存器
        if addr == 0x38:  # FRAME_CNT
            return self._frame_count
        elif addr == 0x3C:  # TIMESTAMP
            return self._timestamp
        elif addr == 0x2C:  # ENC_X_POS
            return self._enc_x
        elif addr == 0x30:  # ENC_Y_POS
            return self._enc_y
        elif addr == 0x34:  # ENC_Z_POS
            return self._enc_z
        
        value = self._registers.get(addr, 0)
        logger.debug(f"SimFPGA: Read reg[0x{addr:02X}] = 0x{value:08X}")
        return value
    
    def configure_pso(self, config: TriggerConfig) -> bool:
        """配置PSO"""
        if not config.validate():
            logger.error("Invalid PSO config")
            return False
        
        self._pso_config = config
        logger.info(
            f"SimFPGA: PSO configured - "
            f"start={config.start_pos}, end={config.end_pos}, interval={config.interval}"
        )
        self._state = DeviceState.READY
        return True
    
    def start_pso(self) -> bool:
        """启动PSO"""
        if not self._pso_config:
            logger.error("PSO not configured")
            return False
        
        self._pso_running = True
        self._pso_position = self._pso_config.start_pos
        self._state = DeviceState.BUSY
        logger.info("SimFPGA: PSO started")
        return True
    
    def stop_pso(self) -> bool:
        """停止PSO"""
        self._pso_running = False
        self._state = DeviceState.IDLE
        logger.info("SimFPGA: PSO stopped")
        return True
    
    def simulate_motion_step(self, delta_x: float = 0.1) -> int:
        """模拟运动步进并返回触发次数
        
        Args:
            delta_x: X轴移动距离（μm）
            
        Returns:
            int: 触发次数
        """
        if not self._pso_running or not self._pso_config:
            return 0
        
        # 更新位置
        self._pso_position += delta_x
        self._enc_x = int(self._pso_position * 1000)  # μm to nm
        
        # 检查是否触发
        triggers = 0
        if self._pso_position >= self._pso_config.start_pos and \
           self._pso_position <= self._pso_config.end_pos:
            # 计算应该触发的次数
            pos_in_range = self._pso_position - self._pso_config.start_pos
            expected_triggers = int(pos_in_range / self._pso_config.interval) + 1
            
            if expected_triggers > self._frame_count:
                triggers = expected_triggers - self._frame_count
                self._frame_count = expected_triggers
        
        # 更新时间戳（模拟）
        self._timestamp += 1
        
        return triggers
    
    def get_encoder_position(self, axis: str) -> float:
        """获取编码器位置"""
        axis = axis.lower()
        if axis == 'x':
            return self._enc_x / 1000.0  # nm to μm
        elif axis == 'y':
            return self._enc_y / 1000.0
        elif axis == 'z':
            return self._enc_z / 1000.0
        return 0.0
    
    def get_frame_count(self) -> int:
        """获取帧计数"""
        return self._frame_count
    
    def get_timestamp(self) -> int:
        """获取时间戳"""
        return self._timestamp
    
    def set_pwm(self, channel: int, period_ns: int, duty: float) -> bool:
        """设置PWM"""
        logger.debug(f"SimFPGA: PWM[{channel}] = period:{period_ns}ns, duty:{duty:.2%}")
        return True


__all__ = ["SimFPGA"]
