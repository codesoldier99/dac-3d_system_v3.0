"""
运动台模拟驱动
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, List

from dac3d.hal.interfaces import IStage, Position, DeviceState


logger = logging.getLogger(__name__)


class SimStage(IStage):
    """运动台模拟器
    
    模拟XY/Z轴运动，支持位置反馈
    """
    
    def __init__(
        self,
        device_id: str = "sim_stage",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(device_id, config)
        
        # 当前位置
        self._position = Position(0, 0, 0)
        self._target_position = Position(0, 0, 0)
        
        # 运动状态
        self._is_moving = False
        self._is_homed = False
        
        # 运动参数
        self._velocity = config.get("velocity", 100.0) if config else 100.0  # mm/s
        self._acceleration = config.get("acceleration", 500.0) if config else 500.0
        
        # 运动线程
        self._motion_thread: Optional[threading.Thread] = None
        self._stop_motion = threading.Event()
        
        logger.info(f"SimStage initialized: {device_id}")
    
    def connect(self) -> bool:
        """模拟连接"""
        logger.info("SimStage: Simulated connection")
        time.sleep(0.05)
        self._state = DeviceState.CONNECTED
        return True
    
    def disconnect(self) -> bool:
        """模拟断开"""
        self.stop(emergency=True)
        self._state = DeviceState.DISCONNECTED
        logger.info("SimStage: Disconnected")
        return True
    
    def reset(self) -> bool:
        """复位"""
        self.stop(emergency=True)
        self._is_homed = False
        logger.info("SimStage: Reset")
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """获取信息"""
        return {
            "device_id": self._device_id,
            "type": "Simulated Stage",
            "position": self._position.to_dict(),
            "is_homed": self._is_homed,
            "is_moving": self._is_moving,
            "state": self._state.name,
        }
    
    def home(self, axes: Optional[List[str]] = None) -> bool:
        """模拟回零"""
        logger.info("SimStage: Homing...")
        self._state = DeviceState.HOMING
        
        time.sleep(0.5)  # 模拟回零时间
        
        self._position = Position(0, 0, 0)
        self._is_homed = True
        self._state = DeviceState.IDLE
        
        logger.info("SimStage: Homed")
        return True
    
    def move_to(
        self,
        pos: Position,
        wait: bool = True,
        velocity: Optional[float] = None
    ) -> bool:
        """移动到目标位置"""
        self._target_position = pos
        vel = velocity if velocity else self._velocity
        
        # 计算运动时间
        distance = ((pos.x - self._position.x)**2 + 
                   (pos.y - self._position.y)**2 + 
                   (pos.z - self._position.z)**2)**0.5
        
        motion_time = distance / vel if vel > 0 else 0
        
        logger.debug(f"SimStage: Moving to {pos}, distance={distance:.2f}mm, time={motion_time:.2f}s")
        
        # 启动运动线程
        self._stop_motion.clear()
        self._motion_thread = threading.Thread(
            target=self._motion_worker,
            args=(pos, motion_time)
        )
        self._motion_thread.start()
        
        if wait:
            self._motion_thread.join()
        
        return True
    
    def _motion_worker(self, target: Position, duration: float):
        """运动工作线程"""
        self._is_moving = True
        self._state = DeviceState.MOVING
        
        start_pos = Position(self._position.x, self._position.y, self._position.z)
        start_time = time.time()
        
        while not self._stop_motion.is_set():
            elapsed = time.time() - start_time
            
            if elapsed >= duration:
                self._position = target
                break
            
            # 线性插值
            progress = elapsed / duration if duration > 0 else 1.0
            self._position = Position(
                start_pos.x + (target.x - start_pos.x) * progress,
                start_pos.y + (target.y - start_pos.y) * progress,
                start_pos.z + (target.z - start_pos.z) * progress
            )
            
            time.sleep(0.01)  # 100Hz更新
        
        self._is_moving = False
        self._state = DeviceState.IDLE
        logger.debug(f"SimStage: Reached {self._position}")
    
    def move_relative(self, delta: Position, wait: bool = True) -> bool:
        """相对移动"""
        target = Position(
            self._position.x + delta.x,
            self._position.y + delta.y,
            self._position.z + delta.z
        )
        return self.move_to(target, wait)
    
    def stop(self, emergency: bool = False) -> bool:
        """停止运动"""
        self._stop_motion.set()
        if self._motion_thread and self._motion_thread.is_alive():
            self._motion_thread.join(timeout=1.0)
        
        self._is_moving = False
        self._state = DeviceState.IDLE
        logger.info("SimStage: Stopped")
        return True
    
    def get_position(self) -> Position:
        """获取当前位置"""
        return Position(self._position.x, self._position.y, self._position.z)
    
    def set_velocity(self, velocity: float, axis: Optional[str] = None) -> bool:
        """设置速度"""
        self._velocity = velocity
        logger.debug(f"SimStage: Velocity set to {velocity} mm/s")
        return True
    
    def set_acceleration(self, accel: float, axis: Optional[str] = None) -> bool:
        """设置加速度"""
        self._acceleration = accel
        logger.debug(f"SimStage: Acceleration set to {accel} mm/s²")
        return True
    
    @property
    def is_moving(self) -> bool:
        """是否正在运动"""
        return self._is_moving
    
    @property
    def is_homed(self) -> bool:
        """是否已回零"""
        return self._is_homed


__all__ = ["SimStage"]
