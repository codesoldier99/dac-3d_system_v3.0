"""
PI压电台驱动

支持PI E-709/E-725等压电控制器
主要用于Z轴纳米精度定位和聚焦
"""

import time
import logging
from typing import Dict, Any, Optional, List

from dac3d.hal.interfaces import IStage, Position, DeviceState


logger = logging.getLogger(__name__)


class PIPiezoError(Exception):
    """PI压电台错误"""
    pass


class PIPiezoStage(IStage):
    """PI压电台驱动
    
    封装PI GCS(General Command Set)命令
    支持串口、USB、TCP连接
    """
    
    def __init__(
        self,
        device_id: str = "pi_piezo_z",
        connection_type: str = "tcp",
        address: str = "192.168.1.20",
        axis_name: str = "1",
        config: Optional[Dict[str, Any]] = None
    ):
        """初始化
        
        Args:
            device_id: 设备ID
            connection_type: 连接类型 ('tcp', 'usb', 'serial')
            address: 连接地址(IP或COM端口)
            axis_name: 轴名称(PI使用字符串标识轴)
            config: 配置字典
        """
        super().__init__(device_id, config)
        
        self._conn_type = connection_type
        self._address = address
        self._axis = axis_name
        
        self._controller = None
        self._pi_dll = None
        
        # 行程范围(μm)
        self._range_min = config.get("range_min", 0.0) if config else 0.0
        self._range_max = config.get("range_max", 100.0) if config else 100.0
        
        # 伺服参数
        self._servo_enabled = False
        self._is_homed = False
        
        # 当前位置
        self._current_z = 0.0
        
        logger.info(f"PIPiezoStage initialized: {connection_type}={address}, axis={axis_name}")
    
    def _load_pi_library(self) -> bool:
        """加载PI库
        
        尝试使用pipython库(推荐)或直接调用GCS DLL
        """
        try:
            # 方法1: 使用pipython(Python官方库)
            try:
                from pipython import GCSDevice
                self._pi_dll = GCSDevice
                logger.info("Using pipython library")
                return True
            except ImportError:
                pass
            
            # 方法2: 直接加载GCS DLL(备选)
            import ctypes
            dll_path = "PI_GCS2_DLL.dll"
            self._pi_dll = ctypes.windll.LoadLibrary(dll_path)
            logger.info("Using PI GCS DLL directly")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load PI library: {e}")
            return False
    
    def connect(self) -> bool:
        """连接到PI控制器"""
        try:
            # 加载PI库
            if not self._load_pi_library():
                self._error_msg = "Failed to load PI library"
                return False
            
            # 创建控制器实例
            if hasattr(self._pi_dll, '__call__'):
                # 使用pipython
                self._controller = self._pi_dll()
                
                # 根据连接类型连接
                if self._conn_type == "tcp":
                    self._controller.ConnectTCPIP(ipaddress=self._address)
                elif self._conn_type == "usb":
                    self._controller.ConnectUSB(serialnum=self._address)
                elif self._conn_type == "serial":
                    self._controller.ConnectRS232(comport=int(self._address), baudrate=115200)
                else:
                    raise PIPiezoError(f"Unsupported connection type: {self._conn_type}")
                
                logger.info(f"Connected to PI controller: {self._controller.qIDN()}")
            else:
                # 使用GCS DLL
                # TODO: 实现直接DLL调用
                raise NotImplementedError("Direct DLL call not implemented yet")
            
            # 使能伺服
            self._enable_servo()
            
            self._state = DeviceState.CONNECTED
            return True
            
        except Exception as e:
            self._error_msg = f"Connection error: {e}"
            logger.error(self._error_msg)
            self._state = DeviceState.ERROR
            return False
    
    def disconnect(self) -> bool:
        """断开连接"""
        try:
            if self._controller:
                # 禁用伺服
                self._disable_servo()
                
                # 关闭连接
                self._controller.CloseConnection()
                self._controller = None
            
            self._state = DeviceState.DISCONNECTED
            logger.info("Disconnected from PI controller")
            return True
            
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return False
    
    def reset(self) -> bool:
        """复位控制器"""
        try:
            if self._controller:
                # PI控制器复位
                self._controller.RBT()  # Reboot
                time.sleep(2.0)
                
                # 重新使能伺服
                self._enable_servo()
            
            logger.info("PI controller reset")
            return True
            
        except Exception as e:
            logger.error(f"Reset error: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取设备信息"""
        info = {
            "device_id": self._device_id,
            "type": "PI Piezo Stage",
            "connection": f"{self._conn_type}:{self._address}",
            "axis": self._axis,
            "range": f"{self._range_min}-{self._range_max} μm",
            "servo_enabled": self._servo_enabled,
            "is_homed": self._is_homed,
            "state": self._state.name,
        }
        
        if self._controller:
            try:
                info["controller_id"] = self._controller.qIDN()
            except:
                pass
        
        return info
    
    def _enable_servo(self) -> bool:
        """使能伺服"""
        try:
            if self._controller:
                self._controller.SVO(self._axis, True)
                self._servo_enabled = True
                logger.info("Servo enabled")
                return True
            return False
        except Exception as e:
            logger.error(f"Enable servo error: {e}")
            return False
    
    def _disable_servo(self) -> bool:
        """禁用伺服"""
        try:
            if self._controller:
                self._controller.SVO(self._axis, False)
                self._servo_enabled = False
                logger.info("Servo disabled")
                return True
            return False
        except Exception as e:
            logger.error(f"Disable servo error: {e}")
            return False
    
    def home(self, axes: Optional[List[str]] = None) -> bool:
        """回零(参考点搜索)
        
        PI压电台的"回零"实际是查找参考点(REF)
        """
        try:
            if not self._controller:
                return False
            
            self._state = DeviceState.HOMING
            logger.info("Searching reference point...")
            
            # 启动参考点搜索
            self._controller.FRF(self._axis)
            
            # 等待完成
            timeout = 30.0  # 秒
            start_time = time.time()
            
            while True:
                # 查询是否完成
                is_referenced = self._controller.qFRF(self._axis)[self._axis]
                if is_referenced:
                    break
                
                if time.time() - start_time > timeout:
                    raise PIPiezoError("Homing timeout")
                
                time.sleep(0.1)
            
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
        """移动到指定Z位置
        
        Args:
            pos: 目标位置(只使用z值，单位μm)
            wait: 是否等待运动完成
            velocity: PI压电台速度通常由控制器自动控制
        """
        try:
            if not self._controller:
                return False
            
            target_z = pos.z
            
            # 检查范围
            if not (self._range_min <= target_z <= self._range_max):
                self._error_msg = f"Position {target_z} out of range [{self._range_min}, {self._range_max}]"
                logger.error(self._error_msg)
                return False
            
            # 移动指令
            self._controller.MOV(self._axis, target_z)
            self._state = DeviceState.MOVING
            
            logger.debug(f"Moving to Z={target_z} μm")
            
            # 等待运动完成
            if wait:
                self._wait_on_target()
                self._state = DeviceState.IDLE
                self._current_z = self.get_position().z
                logger.debug(f"Move completed, Z={self._current_z}")
            
            return True
            
        except Exception as e:
            self._error_msg = f"Move error: {e}"
            logger.error(self._error_msg)
            self._state = DeviceState.ERROR
            return False
    
    def move_relative(self, delta: Position, wait: bool = True) -> bool:
        """相对移动"""
        try:
            if not self._controller:
                return False
            
            # PI的相对移动命令
            self._controller.MVR(self._axis, delta.z)
            self._state = DeviceState.MOVING
            
            if wait:
                self._wait_on_target()
                self._state = DeviceState.IDLE
                self._current_z = self.get_position().z
            
            return True
            
        except Exception as e:
            logger.error(f"Relative move error: {e}")
            return False
    
    def stop(self, emergency: bool = False) -> bool:
        """停止运动"""
        try:
            if self._controller:
                if emergency:
                    # 紧急停止
                    self._controller.STP()
                else:
                    # 平滑停止(PI自动减速)
                    self._controller.HLT(self._axis)
                
                self._state = DeviceState.IDLE
                logger.info("Motion stopped")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Stop error: {e}")
            return False
    
    def get_position(self) -> Position:
        """获取当前Z位置"""
        try:
            if self._controller:
                # 查询当前位置
                pos_z = self._controller.qPOS(self._axis)[self._axis]
                self._current_z = pos_z
                return Position(0, 0, pos_z)
            return Position(0, 0, self._current_z)
            
        except Exception as e:
            logger.error(f"Get position error: {e}")
            return Position(0, 0, self._current_z)
    
    def set_velocity(self, velocity: float, axis: Optional[str] = None) -> bool:
        """设置速度
        
        注意: PI压电台的速度通常由控制器自动优化，
        部分型号支持通过VEL命令设置
        """
        try:
            if self._controller:
                # 尝试设置速度(并非所有型号都支持)
                try:
                    self._controller.VEL(self._axis, velocity)
                    logger.debug(f"Velocity set to {velocity}")
                    return True
                except:
                    logger.warning("VEL command not supported by this controller")
                    return False
            return False
            
        except Exception as e:
            logger.error(f"Set velocity error: {e}")
            return False
    
    def set_acceleration(self, accel: float, axis: Optional[str] = None) -> bool:
        """设置加速度
        
        PI压电台通常不支持手动设置加速度
        """
        logger.warning("PI piezo does not support manual acceleration setting")
        return False
    
    @property
    def is_moving(self) -> bool:
        """是否正在运动"""
        try:
            if self._controller:
                # 查询是否到达目标位置
                on_target = self._controller.qONT(self._axis)[self._axis]
                return not on_target
            return False
        except:
            return False
    
    @property
    def is_homed(self) -> bool:
        """是否已回零"""
        return self._is_homed
    
    def _wait_on_target(self, timeout: float = 10.0) -> bool:
        """等待到达目标位置
        
        Args:
            timeout: 超时时间(秒)
            
        Returns:
            bool: 成功返回True
        """
        start_time = time.time()
        
        while True:
            if not self.is_moving:
                return True
            
            if time.time() - start_time > timeout:
                logger.error("Wait on target timeout")
                return False
            
            time.sleep(0.01)
    
    def get_voltage(self) -> float:
        """获取当前输出电压
        
        Returns:
            float: 电压值(V)
        """
        try:
            if self._controller:
                voltage = self._controller.qVOL(self._axis)[self._axis]
                return voltage
            return 0.0
        except Exception as e:
            logger.error(f"Get voltage error: {e}")
            return 0.0
    
    def set_voltage(self, voltage: float) -> bool:
        """直接设置输出电压(开环模式)
        
        警告: 仅在特殊情况下使用，正常应使用闭环MOV命令
        
        Args:
            voltage: 电压值(V)
        """
        try:
            if self._controller:
                # 切换到开环模式
                self._controller.SVO(self._axis, False)
                
                # 设置电压
                self._controller.SVA(self._axis, voltage)
                
                logger.warning(f"Open-loop voltage set to {voltage}V")
                return True
            return False
        except Exception as e:
            logger.error(f"Set voltage error: {e}")
            return False


__all__ = ["PIPiezoStage", "PIPiezoError"]
