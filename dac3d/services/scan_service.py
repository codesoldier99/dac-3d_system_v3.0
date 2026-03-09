"""
扫描服务

负责协调硬件执行扫描任务
"""

import logging
import time
from typing import Dict, Any, Optional, List
import numpy as np
from numpy.typing import NDArray

from dac3d.hal.interfaces import (
    IStage, ICamera, IFPGA, Position, ScanRegion, TriggerConfig
)
from dac3d.hal.camera.camera_array import CameraArray
from dac3d.core.state_machine import ScanStateMachine, ScanState
from dac3d.core.event_bus import event_bus, Event, EventNames
from dac3d.core.exceptions import ScanError


logger = logging.getLogger(__name__)


class ScanService:
    """扫描服务
    
    协调运动台、FPGA、相机完成扫描任务
    """
    
    def __init__(
        self,
        stage_xy: IStage,
        stage_z: IStage,
        fpga: IFPGA,
        camera_array: CameraArray
    ):
        """初始化
        
        Args:
            stage_xy: XY运动台
            stage_z: Z轴(压电台)
            fpga: FPGA控制器
            camera_array: 相机阵列
        """
        self._stage_xy = stage_xy
        self._stage_z = stage_z
        self._fpga = fpga
        self._cameras = camera_array
        
        # 状态机
        self._state_machine = ScanStateMachine()
        
        # 扫描参数
        self._scan_region: Optional[ScanRegion] = None
        self._z_stack_config: Optional[Dict] = None
        
        # 扫描数据
        self._scan_data: Dict[str, List[NDArray]] = {}
        
        logger.info("ScanService initialized")
    
    def initialize_system(self) -> bool:
        """初始化系统
        
        Returns:
            bool: 成功返回True
        """
        try:
            self._state_machine.initialize()
            
            logger.info("Connecting hardware...")
            
            # 连接所有设备
            if not self._stage_xy.connect():
                raise ScanError("XY stage connection failed")
            
            if not self._stage_z.connect():
                raise ScanError("Z stage connection failed")
            
            if not self._fpga.connect():
                raise ScanError("FPGA connection failed")
            
            if not self._cameras.connect_all():
                raise ScanError("Camera connection failed")
            
            self._state_machine.init_done()
            
            event_bus.publish(Event(
                name=EventNames.HARDWARE_CONNECTED,
                data={"message": "All hardware connected"},
                source="scan_service"
            ))
            
            logger.info("System initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            self._state_machine.error()
            return False
    
    def home_all_axes(self) -> bool:
        """所有轴回零
        
        Returns:
            bool: 成功返回True
        """
        try:
            # 根据当前状态，转换到HOMING状态
            current_state = self._state_machine.get_current_state()
            logger.info(f"Current state: {current_state.name}")
            
            if current_state == ScanState.IDLE:
                # 从IDLE状态需要先初始化
                self._state_machine.initialize()
                self._state_machine.init_done()  # 转换到HOMING状态
            elif current_state == ScanState.READY:
                # 从READY状态需要先回到合适的状态
                # 添加一个临时的错误恢复来重新进入IDLE
                self._state_machine.abort()  # 回到IDLE
                self._state_machine.initialize()
                self._state_machine.init_done()  # 转换到HOMING状态
            elif current_state != ScanState.HOMING:
                # 如果当前状态不是HOMING，先中止到IDLE
                self._state_machine.abort()
                self._state_machine.initialize()
                self._state_machine.init_done()
            
            logger.info("Homing all axes...")
            
            # XY轴回零
            if not self._stage_xy.home():
                raise ScanError("XY homing failed")
            
            # Z轴回零
            if not self._stage_z.home():
                raise ScanError("Z homing failed")
            
            # 回零完成，转换到READY状态
            self._state_machine.home_done()
            
            logger.info("Homing completed")
            return True
            
        except Exception as e:
            logger.error(f"Homing failed: {e}")
            self._state_machine.error()
            return False
    
    def configure_scan(
        self,
        region: ScanRegion,
        z_stack: Optional[Dict] = None
    ) -> bool:
        """配置扫描参数
        
        Args:
            region: 扫描区域
            z_stack: Z轴堆栈配置 {"start": 0, "end": 100, "step": 1}
            
        Returns:
            bool: 成功返回True
        """
        try:
            if self._state_machine.get_current_state() != ScanState.READY:
                raise ScanError("System not ready")
            
            self._state_machine.configure()
            
            self._scan_region = region
            self._z_stack_config = z_stack
            
            # 配置FPGA PSO触发
            trigger_config = TriggerConfig(
                mode='position',
                start_pos=region.start.x,
                end_pos=region.end.x,
                interval=region.step_x,
                pulse_width_ns=1000,
                axis='x'
            )
            
            if not self._fpga.configure_pso(trigger_config):
                raise ScanError("FPGA PSO configuration failed")
            
            # 配置相机触发模式
            from dac3d.hal.interfaces import TriggerMode
            if not self._cameras.set_trigger_mode_all(TriggerMode.HARDWARE, "Line1"):
                raise ScanError("Camera trigger configuration failed")
            
            self._state_machine.config_done()
            
            logger.info(f"Scan configured: {region.total_points} points")
            return True
            
        except Exception as e:
            logger.error(f"Scan configuration failed: {e}")
            self._state_machine.error()
            return False
    
    def execute_scan(self) -> bool:
        """执行扫描
        
        Returns:
            bool: 成功返回True
        """
        try:
            if not self._scan_region:
                raise ScanError("Scan not configured")
            
            self._state_machine.start_scan()
            
            event_bus.publish(Event(
                name=EventNames.SCAN_STARTED,
                data={"region": self._scan_region},
                source="scan_service"
            ))
            
            # 移动到起始位置
            logger.info(f"Moving to start position: {self._scan_region.start}")
            if not self._stage_xy.move_to(self._scan_region.start, wait=True):
                raise ScanError("Failed to move to start position")
            
            self._state_machine.at_start()
            
            # 启动相机采集
            if not self._cameras.start_acquisition_all():
                raise ScanError("Failed to start camera acquisition")
            
            # 执行扫描
            self._scan_data = self._perform_scan()
            
            # 停止相机
            self._cameras.stop_acquisition_all()
            
            self._state_machine.scan_done()
            
            event_bus.publish(Event(
                name=EventNames.SCAN_COMPLETED,
                data={"n_frames": sum(len(imgs) for imgs in self._scan_data.values())},
                source="scan_service"
            ))
            
            logger.info("Scan completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Scan execution failed: {e}")
            self._state_machine.error()
            return False
    
    def _perform_scan(self) -> Dict[str, List[NDArray]]:
        """执行实际扫描
        
        Returns:
            Dict: {camera_id: [images]}
        """
        region = self._scan_region
        scan_data = {cam.device_id: [] for cam in self._cameras.cameras}
        
        # 扫描Y方向的每一行
        for iy in range(region.n_points_y):
            y_pos = region.start.y + iy * region.step_y
            
            logger.info(f"Scanning row {iy+1}/{region.n_points_y}, Y={y_pos:.2f}")
            
            # 移动到行起点
            row_start = Position(region.start.x, y_pos, region.start.z)
            self._stage_xy.move_to(row_start, wait=True)
            
            # 配置FPGA PSO (每行都重新配置)
            trigger_config = TriggerConfig(
                mode='position',
                start_pos=region.start.x,
                end_pos=region.end.x,
                interval=region.step_x,
                pulse_width_ns=1000,
                axis='x'
            )
            self._fpga.configure_pso(trigger_config)
            
            # 启动PSO
            self._fpga.start_pso()
            
            # X方向匀速扫描
            row_end = Position(region.end.x, y_pos, region.start.z)
            velocity = 10.0  # mm/s, 根据需要调整
            self._stage_xy.move_to(row_end, wait=False, velocity=velocity)
            
            # 抓取图像序列
            images = self._cameras.grab_sequence_all(
                n_frames=region.n_points_x,
                timeout_ms=30000
            )
            
            # 等待运动完成
            while self._stage_xy.is_moving:
                time.sleep(0.01)
            
            # 停止PSO
            self._fpga.stop_pso()
            
            # 收集数据
            for cam_id, imgs in images.items():
                scan_data[cam_id].extend(imgs)
            
            # 发布进度
            progress = (iy + 1) / region.n_points_y
            event_bus.publish(Event(
                name=EventNames.SCAN_PROGRESS,
                data={"progress": progress, "row": iy + 1},
                source="scan_service"
            ))
        
        return scan_data
    
    def get_scan_data(self) -> Dict[str, List[NDArray]]:
        """获取扫描数据
        
        Returns:
            Dict: 扫描数据
        """
        return self._scan_data
    
    def stop_scan(self) -> bool:
        """停止扫描"""
        try:
            self._fpga.stop_pso()
            self._cameras.stop_acquisition_all()
            self._stage_xy.stop(emergency=False)
            
            self._state_machine.abort()
            
            logger.info("Scan stopped")
            return True
        except Exception as e:
            logger.error(f"Stop scan error: {e}")
            return False
    
    @property
    def state(self) -> ScanState:
        """当前状态"""
        return self._state_machine.get_current_state()


__all__ = ["ScanService"]
