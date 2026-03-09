"""
Basler工业相机驱动

使用pypylon库控制Basler相机
支持硬件触发、序列采集等高级功能
"""

import time
import logging
from typing import Dict, Any, Optional, List
import numpy as np
from numpy.typing import NDArray

from dac3d.hal.interfaces import (
    ICamera,
    DeviceState,
    TriggerMode,
    CameraConfig,
)


logger = logging.getLogger(__name__)


class BaslerError(Exception):
    """Basler相机错误"""
    pass


class BaslerCamera(ICamera):
    """Basler相机驱动
    
    封装pypylon库，提供统一接口
    """
    
    def __init__(
        self,
        device_id: str = "basler_cam",
        serial_number: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """初始化
        
        Args:
            device_id: 设备ID
            serial_number: 相机序列号(None则使用第一台)
            config: 配置字典
        """
        super().__init__(device_id, config)
        
        self._serial_number = serial_number
        self._camera = None
        self._converter = None
        
        # 图像参数
        self._width = 0
        self._height = 0
        self._frame_count = 0
        
        # 默认配置
        self._camera_config = CameraConfig(
            exposure_us=config.get("exposure_us", 1000.0) if config else 1000.0,
            gain=config.get("gain", 0.0) if config else 0.0,
            trigger_mode=config.get("trigger_mode", "hardware") if config else "hardware",
            trigger_source=config.get("trigger_source", "Line1") if config else "Line1",
        )
        
        logger.info(f"BaslerCamera initialized: SN={serial_number}")
    
    def _import_pypylon(self) -> bool:
        """导入pypylon库"""
        try:
            from pypylon import pylon
            self._pylon = pylon
            logger.info("pypylon imported successfully")
            return True
        except ImportError as e:
            self._error_msg = f"Failed to import pypylon: {e}"
            logger.error(self._error_msg)
            return False
    
    def connect(self) -> bool:
        """连接相机"""
        try:
            # 导入库
            if not self._import_pypylon():
                return False
            
            # 创建相机实例工厂
            tlFactory = self._pylon.TlFactory.GetInstance()
            
            # 枚举相机
            devices = tlFactory.EnumerateDevices()
            if len(devices) == 0:
                self._error_msg = "No Basler camera found"
                logger.error(self._error_msg)
                return False
            
            # 选择相机
            if self._serial_number:
                # 按序列号查找
                device_info = None
                for dev in devices:
                    if dev.GetSerialNumber() == self._serial_number:
                        device_info = dev
                        break
                
                if not device_info:
                    self._error_msg = f"Camera with SN={self._serial_number} not found"
                    logger.error(self._error_msg)
                    return False
            else:
                # 使用第一台
                device_info = devices[0]
                logger.warning("No serial number specified, using first camera")
            
            # 创建相机实例
            self._camera = self._pylon.InstantCamera(tlFactory.CreateDevice(device_info))
            
            # 打开相机
            self._camera.Open()
            
            logger.info(
                f"Connected to camera: "
                f"Model={self._camera.GetDeviceInfo().GetModelName()}, "
                f"SN={self._camera.GetDeviceInfo().GetSerialNumber()}"
            )
            
            # 获取图像尺寸
            self._width = self._camera.Width.GetValue()
            self._height = self._camera.Height.GetValue()
            
            # 创建图像格式转换器
            self._converter = self._pylon.ImageFormatConverter()
            self._converter.OutputPixelFormat = self._pylon.PixelType_Mono16
            self._converter.OutputBitAlignment = self._pylon.OutputBitAlignment_MsbAligned
            
            # 应用配置
            self._apply_config()
            
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
            if self._camera:
                if self._camera.IsGrabbing():
                    self._camera.StopGrabbing()
                
                self._camera.Close()
                self._camera = None
            
            self._state = DeviceState.DISCONNECTED
            logger.info("Disconnected from camera")
            return True
            
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return False
    
    def reset(self) -> bool:
        """复位相机"""
        try:
            if self._camera:
                # 停止采集
                if self._camera.IsGrabbing():
                    self._camera.StopGrabbing()
                
                # 重置计数器
                self._frame_count = 0
                
                logger.info("Camera reset")
            return True
        except Exception as e:
            logger.error(f"Reset error: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取相机信息"""
        info = {
            "device_id": self._device_id,
            "type": "Basler Camera",
            "width": self._width,
            "height": self._height,
            "frame_count": self._frame_count,
            "state": self._state.name,
        }
        
        if self._camera:
            try:
                dev_info = self._camera.GetDeviceInfo()
                info.update({
                    "model": dev_info.GetModelName(),
                    "serial_number": dev_info.GetSerialNumber(),
                    "firmware": dev_info.GetDeviceVersion(),
                })
            except:
                pass
        
        return info
    
    def _apply_config(self) -> None:
        """应用相机配置"""
        try:
            # 设置曝光
            self.set_exposure(self._camera_config.exposure_us)
            
            # 设置增益
            self.set_gain(self._camera_config.gain)
            
            # 设置触发模式
            mode_map = {
                "software": TriggerMode.SOFTWARE,
                "hardware": TriggerMode.HARDWARE,
                "continuous": TriggerMode.CONTINUOUS,
            }
            self.set_trigger_mode(
                mode_map.get(self._camera_config.trigger_mode, TriggerMode.HARDWARE),
                self._camera_config.trigger_source
            )
            
            logger.info("Camera configuration applied")
            
        except Exception as e:
            logger.error(f"Apply config error: {e}")
    
    def set_exposure(self, exposure_us: float) -> bool:
        """设置曝光时间"""
        try:
            if self._camera:
                self._camera.ExposureTime.SetValue(exposure_us)
                self._camera_config.exposure_us = exposure_us
                logger.debug(f"Exposure set to {exposure_us} μs")
                return True
            return False
        except Exception as e:
            logger.error(f"Set exposure error: {e}")
            return False
    
    def set_gain(self, gain: float) -> bool:
        """设置增益"""
        try:
            if self._camera:
                # Basler使用Gain(Raw)或Gain(dB)
                if self._camera.Gain.GetAccessMode() == self._pylon.AccessModeType_RW:
                    self._camera.Gain.SetValue(gain)
                    self._camera_config.gain = gain
                    logger.debug(f"Gain set to {gain} dB")
                    return True
            return False
        except Exception as e:
            logger.error(f"Set gain error: {e}")
            return False
    
    def set_roi(self, x: int, y: int, width: int, height: int) -> bool:
        """设置ROI"""
        try:
            if self._camera:
                # Basler ROI设置
                self._camera.OffsetX.SetValue(0)  # 先设为0避免超限
                self._camera.OffsetY.SetValue(0)
                
                self._camera.Width.SetValue(width)
                self._camera.Height.SetValue(height)
                self._camera.OffsetX.SetValue(x)
                self._camera.OffsetY.SetValue(y)
                
                self._width = width
                self._height = height
                
                logger.debug(f"ROI set to ({x}, {y}, {width}, {height})")
                return True
            return False
        except Exception as e:
            logger.error(f"Set ROI error: {e}")
            return False
    
    def set_trigger_mode(self, mode: TriggerMode, source: str = "Line1") -> bool:
        """设置触发模式"""
        try:
            if not self._camera:
                return False
            
            if mode == TriggerMode.CONTINUOUS or mode == TriggerMode.FREERUN:
                # 连续模式(关闭触发)
                self._camera.TriggerMode.SetValue("Off")
                logger.debug("Trigger mode: Continuous")
                
            elif mode == TriggerMode.SOFTWARE:
                # 软件触发
                self._camera.TriggerMode.SetValue("On")
                self._camera.TriggerSource.SetValue("Software")
                logger.debug("Trigger mode: Software")
                
            elif mode == TriggerMode.HARDWARE:
                # 硬件触发
                self._camera.TriggerMode.SetValue("On")
                self._camera.TriggerSource.SetValue(source)
                self._camera.TriggerActivation.SetValue("RisingEdge")
                logger.debug(f"Trigger mode: Hardware ({source}, RisingEdge)")
            
            self._camera_config.trigger_mode = mode.value
            self._camera_config.trigger_source = source
            return True
            
        except Exception as e:
            logger.error(f"Set trigger mode error: {e}")
            return False
    
    def start_acquisition(self) -> bool:
        """开始采集"""
        try:
            if self._camera and not self._camera.IsGrabbing():
                # 连续采集模式
                self._camera.StartGrabbing(self._pylon.GrabStrategy_LatestImageOnly)
                self._state = DeviceState.ACQUIRING
                logger.debug("Acquisition started")
                return True
            return False
        except Exception as e:
            logger.error(f"Start acquisition error: {e}")
            return False
    
    def stop_acquisition(self) -> bool:
        """停止采集"""
        try:
            if self._camera and self._camera.IsGrabbing():
                self._camera.StopGrabbing()
                self._state = DeviceState.IDLE
                logger.debug("Acquisition stopped")
                return True
            return False
        except Exception as e:
            logger.error(f"Stop acquisition error: {e}")
            return False
    
    def grab(self, timeout_ms: int = 5000) -> Optional[NDArray[np.uint16]]:
        """抓取一帧图像"""
        try:
            if not self._camera:
                return None
            
            # 确保正在采集
            if not self._camera.IsGrabbing():
                self.start_acquisition()
            
            # 等待图像
            grab_result = self._camera.RetrieveResult(
                timeout_ms,
                self._pylon.TimeoutHandling_ThrowException
            )
            
            if grab_result.GrabSucceeded():
                # 转换图像格式
                image = self._converter.Convert(grab_result)
                img_array = image.GetArray()
                
                self._frame_count += 1
                
                grab_result.Release()
                
                logger.debug(f"Grabbed frame {self._frame_count}")
                return img_array
            else:
                logger.error(f"Grab failed: {grab_result.ErrorDescription}")
                grab_result.Release()
                return None
                
        except Exception as e:
            logger.error(f"Grab error: {e}")
            return None
    
    def grab_sequence(
        self,
        n_frames: int,
        timeout_ms: int = 30000
    ) -> List[NDArray[np.uint16]]:
        """抓取序列图像"""
        images = []
        
        try:
            if not self._camera:
                return images
            
            # 设置为序列模式
            if not self._camera.IsGrabbing():
                self._camera.StartGrabbing(self._pylon.GrabStrategy_OneByOne)
            
            # 计算每帧超时
            per_frame_timeout = min(timeout_ms // n_frames, 5000)
            
            # 循环抓取
            start_time = time.time()
            for i in range(n_frames):
                # 检查总超时
                if (time.time() - start_time) * 1000 > timeout_ms:
                    logger.error(f"Sequence timeout after {i} frames")
                    break
                
                # 抓取一帧
                img = self.grab(per_frame_timeout)
                if img is not None:
                    images.append(img)
                else:
                    logger.warning(f"Failed to grab frame {i+1}/{n_frames}")
            
            logger.info(f"Grabbed {len(images)}/{n_frames} frames")
            return images
            
        except Exception as e:
            logger.error(f"Grab sequence error: {e}")
            return images
    
    def get_frame_count(self) -> int:
        """获取已采集帧数"""
        return self._frame_count
    
    @property
    def width(self) -> int:
        """图像宽度"""
        return self._width
    
    @property
    def height(self) -> int:
        """图像高度"""
        return self._height
    
    def trigger_software(self) -> bool:
        """发送软件触发信号
        
        仅在软件触发模式下有效
        """
        try:
            if self._camera and self._camera.TriggerMode.GetValue() == "On":
                if self._camera.TriggerSource.GetValue() == "Software":
                    self._camera.TriggerSoftware.Execute()
                    logger.debug("Software trigger executed")
                    return True
            return False
        except Exception as e:
            logger.error(f"Software trigger error: {e}")
            return False


__all__ = ["BaslerCamera", "BaslerError"]
