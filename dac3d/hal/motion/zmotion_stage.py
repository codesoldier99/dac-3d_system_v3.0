"""
ZMotion运动控制卡驱动

支持ZMC系列控制卡(ZMC408, ZMC432等)
主要用于XY轴大行程扫描
"""

import ctypes
import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from dac3d.hal.interfaces import IStage, Position, DeviceState


logger = logging.getLogger(__name__)


class ZMotionError(Exception):
    """ZMotion错误异常"""
    pass


class ZMotionStage(IStage):
    """ZMotion XY运动台驱动
    
    封装ZMotion控制卡的DLL调用，提供标准化接口
    """
    
    def __init__(
        self,
        device_id: str = "zmotion_xy",
        ip_address: str = "192.168.0.11",
        x_axis: int = 0,
        y_axis: int = 1,
        config: Optional[Dict[str, Any]] = None
    ):
        """初始化
        
        Args:
            device_id: 设备ID
            ip_address: 控制卡IP地址
            x_axis: X轴编号
            y_axis: Y轴编号
            config: 配置字典
        """
        super().__init__(device_id, config)
        
        self._ip = ip_address
        self._x_axis = x_axis
        self._y_axis = y_axis
        
        self._handle = None
        self._dll: Optional[ctypes.CDLL] = None
        
        # 运动参数(默认值，可从config覆盖)
        self._speed = config.get("speed", 100.0) if config else 100.0  # mm/s
        self._accel = config.get("accel", 500.0) if config else 500.0  # mm/s²
        self._units_per_mm = config.get("units_per_mm", 1000.0) if config else 1000.0  # 脉冲/mm
        
        # 软限位(mm)
        self._soft_limit_x = config.get("soft_limit_x", [0, 100]) if config else [0, 100]
        self._soft_limit_y = config.get("soft_limit_y", [0, 100]) if config else [0, 100]
        
        # 状态
        self._is_homed = False
        self._current_pos = Position(0, 0, 0)
        
        logger.info(f"ZMotionStage initialized: IP={ip_address}, X={x_axis}, Y={y_axis}")
    
    def _load_dll(self) -> bool:
        """加载ZMotion DLL"""
        try:
            # 尝试多个可能的DLL路径
            dll_paths = [
                "zauxdll.dll",  # 当前目录
                "C:/ZMotion/zauxdll.dll",  # 标准安装路径
                "C:/Program Files/ZMotion/zauxdll.dll",
            ]
            
            for dll_path in dll_paths:
                try:
                    self._dll = ctypes.windll.LoadLibrary(dll_path)
                    logger.info(f"Loaded ZMotion DLL: {dll_path}")
                    return True
                except OSError:
                    continue
            
            logger.error("Failed to load ZMotion DLL")
            return False
            
        except Exception as e:
            logger.error(f"Load DLL error: {e}")
            return False
    
    def connect(self) -> bool:
        """连接到ZMotion控制卡"""
        try:
            # 加载DLL
            if not self._load_dll():
                self._error_msg = "Failed to load ZMotion DLL"
                return False
            
            # 打开连接
            handle = ctypes.c_void_p()
            ret = self._dll.ZAux_OpenEth(
                self._ip.encode('utf-8'),
                ctypes.byref(handle)
            )
            
            if ret != 0:
                self._error_msg = f"Connection failed, error code: {ret}"
                logger.error(self._error_msg)
                return False
            
            self._handle = handle
            logger.info(f"Connected to ZMotion: {self._ip}")
            
            # 初始化轴参数
            self._init_axes()
            
            self._state = DeviceState.CONNECTED
            return True
            
        except Exception as e:
            self._error_msg = f"Connection error: {e}"
            logger.error(self._error_msg)
            self._state = DeviceState.ERROR
            return False
    
    def _init_axes(self) -> None:
        """初始化轴参数"""
        try:
            for axis in [self._x_axis, self._y_axis]:
                # 设置速度
                self._dll.ZAux_Direct_SetSpeed(
                    self._handle,
                    axis,
                    ctypes.c_float(self._speed)
                )
                
                # 设置加速度
                self._dll.ZAux_Direct_SetAccel(
                    self._handle,
                    axis,
                    ctypes.c_float(self._accel)
                )
                
                # 设置减速度
                self._dll.ZAux_Direct_SetDecel(
                    self._handle,
                    axis,
                    ctypes.c_float(self._accel)
                )
                
                # 设置S曲线时间(减少振动)
                self._dll.ZAux_Direct_SetSramp(
                    self._handle,
                    axis,
                    ctypes.c_float(100.0)  # 100ms
                )
            
            logger.info("Axes initialized")
            
        except Exception as e:
            logger.error(f"Init axes error: {e}")
    
    def disconnect(self) -> bool:
        """断开连接"""
        try:
            if self._handle and self._dll:
                self._dll.ZAux_Close(self._handle)
                self._handle = None
            
            self._state = DeviceState.DISCONNECTED
            logger.info("Disconnected from ZMotion")
            return True
            
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return False
    
    def reset(self) -> bool:
        """复位控制器"""
        try:
            # ZMotion没有软复位，执行停止和清除错误
            self.stop(emergency=False)
            
            # 清除所有轴的错误
            for axis in [self._x_axis, self._y_axis]:
                self._dll.ZAux_Direct_ClearAxisError(self._handle, axis)
            
            logger.info("ZMotion reset")
            return True
            
        except Exception as e:
            logger.error(f"Reset error: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取设备信息"""
        return {
            "device_id": self._device_id,
            "type": "ZMotion Controller",
            "ip_address": self._ip,
            "x_axis": self._x_axis,
            "y_axis": self._y_axis,
            "speed": self._speed,
            "accel": self._accel,
            "is_homed": self._is_homed,
            "state": self._state.name,
        }
    
    def home(self, axes: Optional[List[str]] = None) -> bool:
        """回零操作
        
        Args:
            axes: 需要回零的轴，None表示XY都回零
        """
        try:
            if axes is None:
                axes = ['x', 'y']
            
            axes_to_home = []
            if 'x' in axes:
                axes_to_home.append(self._x_axis)
            if 'y' in axes:
                axes_to_home.append(self._y_axis)
            
            self._state = DeviceState.HOMING
            
            for axis in axes_to_home:
                logger.info(f"Homing axis {axis}...")
                
                # 执行回零(根据控制卡配置的回零模式)
                ret = self._dll.ZAux_Direct_Single_Datum(
                    self._handle,
                    axis,
                    ctypes.c_int(1)  # 回零模式1
                )
                
                if ret != 0:
                    raise ZMotionError(f"Home axis {axis} failed: {ret}")
                
                # 等待回零完成
                while True:
                    status = self._get_axis_status(axis)
                    if not status["moving"]:
                        break
                    time.sleep(0.1)
                
                logger.info(f"Axis {axis} homed")
            
            self._is_homed = True
            self._state = DeviceState.IDLE
            logger.info("Homing completed")
            return True
            
        except Exception as e:
            self._error_msg = f"Homing failed: {e}"
            logger.error(self._error_msg)
            self._state = DeviceState.ERROR
            return False
    
    def move_to(
        self,
        pos: Position,
        wait: bool = True,
        velocity: Optional[float] = None
    ) -> bool:
        """移动到指定位置(绝对移动)
        
        Args:
            pos: 目标位置(mm)
            wait: 是否等待运动完成
            velocity: 运动速度(mm/s)，None使用默认速度
        """
        try:
            # 检查软限位
            if not self._check_soft_limits(pos):
                self._error_msg = f"Position out of soft limits: {pos}"
                logger.error(self._error_msg)
                return False
            
            # 设置速度(如果指定)
            if velocity is not None:
                for axis in [self._x_axis, self._y_axis]:
                    self._dll.ZAux_Direct_SetSpeed(
                        self._handle,
                        axis,
                        ctypes.c_float(velocity)
                    )
            
            # 转换单位(mm -> 脉冲)
            target_x = int(pos.x * self._units_per_mm)
            target_y = int(pos.y * self._units_per_mm)
            
            # 多轴联动(直线插补)
            axes = (ctypes.c_int * 2)(self._x_axis, self._y_axis)
            targets = (ctypes.c_float * 2)(float(target_x), float(target_y))
            
            ret = self._dll.ZAux_Direct_MoveAbs(
                self._handle,
                ctypes.c_int(2),  # 轴数
                axes,
                targets
            )
            
            if ret != 0:
                raise ZMotionError(f"Move failed: {ret}")
            
            self._state = DeviceState.MOVING
            logger.debug(f"Moving to {pos}")
            
            # 等待运动完成
            if wait:
                while self.is_moving:
                    time.sleep(0.01)
                self._state = DeviceState.IDLE
                self._current_pos = self.get_position()
                logger.debug(f"Move completed, pos={self._current_pos}")
            
            return True
            
        except Exception as e:
            self._error_msg = f"Move error: {e}"
            logger.error(self._error_msg)
            self._state = DeviceState.ERROR
            return False
    
    def move_relative(self, delta: Position, wait: bool = True) -> bool:
        """相对移动"""
        current = self.get_position()
        target = Position(
            current.x + delta.x,
            current.y + delta.y,
            current.z + delta.z
        )
        return self.move_to(target, wait)
    
    def stop(self, emergency: bool = False) -> bool:
        """停止运动"""
        try:
            if emergency:
                # 紧急停止(立即停止)
                ret = self._dll.ZAux_Direct_Rapidstop(
                    self._handle,
                    ctypes.c_int(self._x_axis)
                )
                if ret == 0:
                    ret = self._dll.ZAux_Direct_Rapidstop(
                        self._handle,
                        ctypes.c_int(self._y_axis)
                    )
            else:
                # 平滑停止(减速停止)
                ret = self._dll.ZAux_Direct_Single_Cancel(
                    self._handle,
                    ctypes.c_int(self._x_axis),
                    ctypes.c_int(2)  # 减速停止
                )
                if ret == 0:
                    ret = self._dll.ZAux_Direct_Single_Cancel(
                        self._handle,
                        ctypes.c_int(self._y_axis),
                        ctypes.c_int(2)
                    )
            
            if ret != 0:
                logger.error(f"Stop failed: {ret}")
                return False
            
            self._state = DeviceState.IDLE
            logger.info("Motion stopped")
            return True
            
        except Exception as e:
            logger.error(f"Stop error: {e}")
            return False
    
    def get_position(self) -> Position:
        """获取当前位置"""
        try:
            # 读取X轴位置
            pos_x_raw = ctypes.c_float()
            self._dll.ZAux_Direct_GetDpos(
                self._handle,
                self._x_axis,
                ctypes.byref(pos_x_raw)
            )
            
            # 读取Y轴位置
            pos_y_raw = ctypes.c_float()
            self._dll.ZAux_Direct_GetDpos(
                self._handle,
                self._y_axis,
                ctypes.byref(pos_y_raw)
            )
            
            # 转换单位(脉冲 -> mm)
            pos = Position(
                x=pos_x_raw.value / self._units_per_mm,
                y=pos_y_raw.value / self._units_per_mm,
                z=0.0
            )
            
            self._current_pos = pos
            return pos
            
        except Exception as e:
            logger.error(f"Get position error: {e}")
            return self._current_pos
    
    def set_velocity(self, velocity: float, axis: Optional[str] = None) -> bool:
        """设置运动速度"""
        try:
            axes_to_set = []
            if axis is None:
                axes_to_set = [self._x_axis, self._y_axis]
            elif axis.lower() == 'x':
                axes_to_set = [self._x_axis]
            elif axis.lower() == 'y':
                axes_to_set = [self._y_axis]
            else:
                logger.error(f"Invalid axis: {axis}")
                return False
            
            for ax in axes_to_set:
                self._dll.ZAux_Direct_SetSpeed(
                    self._handle,
                    ax,
                    ctypes.c_float(velocity)
                )
            
            self._speed = velocity
            logger.debug(f"Velocity set to {velocity} mm/s")
            return True
            
        except Exception as e:
            logger.error(f"Set velocity error: {e}")
            return False
    
    def set_acceleration(self, accel: float, axis: Optional[str] = None) -> bool:
        """设置加速度"""
        try:
            axes_to_set = []
            if axis is None:
                axes_to_set = [self._x_axis, self._y_axis]
            elif axis.lower() == 'x':
                axes_to_set = [self._x_axis]
            elif axis.lower() == 'y':
                axes_to_set = [self._y_axis]
            else:
                return False
            
            for ax in axes_to_set:
                self._dll.ZAux_Direct_SetAccel(self._handle, ax, ctypes.c_float(accel))
                self._dll.ZAux_Direct_SetDecel(self._handle, ax, ctypes.c_float(accel))
            
            self._accel = accel
            return True
            
        except Exception as e:
            logger.error(f"Set acceleration error: {e}")
            return False
    
    @property
    def is_moving(self) -> bool:
        """是否正在运动"""
        try:
            x_status = self._get_axis_status(self._x_axis)
            y_status = self._get_axis_status(self._y_axis)
            return x_status["moving"] or y_status["moving"]
        except:
            return False
    
    @property
    def is_homed(self) -> bool:
        """是否已回零"""
        return self._is_homed
    
    def _get_axis_status(self, axis: int) -> Dict[str, Any]:
        """获取轴状态"""
        try:
            # 读取轴状态
            status = ctypes.c_uint32()
            self._dll.ZAux_Direct_GetAxisStatus(
                self._handle,
                axis,
                ctypes.byref(status)
            )
            
            status_val = status.value
            return {
                "moving": bool(status_val & 0x01),
                "stop": bool(status_val & 0x02),
                "error": bool(status_val & 0x04),
                "limit_positive": bool(status_val & 0x08),
                "limit_negative": bool(status_val & 0x10),
            }
            
        except Exception as e:
            logger.error(f"Get axis status error: {e}")
            return {"moving": False, "stop": True, "error": True}
    
    def _check_soft_limits(self, pos: Position) -> bool:
        """检查软限位"""
        if not (self._soft_limit_x[0] <= pos.x <= self._soft_limit_x[1]):
            return False
        if not (self._soft_limit_y[0] <= pos.y <= self._soft_limit_y[1]):
            return False
        return True


__all__ = ["ZMotionStage", "ZMotionError"]
