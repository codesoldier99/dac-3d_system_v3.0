"""
相机模拟驱动
"""

import logging
import time
from typing import Dict, Any, Optional, List
import numpy as np
from numpy.typing import NDArray

from dac3d.hal.interfaces import ICamera, DeviceState, TriggerMode


logger = logging.getLogger(__name__)


class SimCamera(ICamera):
    """相机模拟器
    
    生成模拟图像数据
    """
    
    def __init__(
        self,
        device_id: str = "sim_camera",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(device_id, config)
        
        # 图像参数（优化：使用更小的图像以节省内存）
        self._width = config.get("width", 512) if config else 512
        self._height = config.get("height", 512) if config else 512
        self._exposure_us = 1000.0
        self._gain = 0.0
        
        # 触发模式
        self._trigger_mode = TriggerMode.SOFTWARE
        self._is_acquiring = False
        
        # 帧计数
        self._frame_count = 0
        
        # 添加模拟瑕疵
        self._defect_probability = 0.1  # 10%概率生成瑕疵
        
        logger.info(f"SimCamera initialized: {device_id}, size={self._width}x{self._height}")
    
    def connect(self) -> bool:
        """模拟连接"""
        logger.info("SimCamera: Simulated connection")
        time.sleep(0.05)
        self._state = DeviceState.CONNECTED
        return True
    
    def disconnect(self) -> bool:
        """模拟断开"""
        self._is_acquiring = False
        self._state = DeviceState.DISCONNECTED
        logger.info("SimCamera: Disconnected")
        return True
    
    def reset(self) -> bool:
        """复位"""
        self._frame_count = 0
        self._is_acquiring = False
        logger.info("SimCamera: Reset")
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """获取信息"""
        return {
            "device_id": self._device_id,
            "type": "Simulated Camera",
            "resolution": f"{self._width}x{self._height}",
            "exposure_us": self._exposure_us,
            "gain": self._gain,
            "frame_count": self._frame_count,
            "state": self._state.name,
        }
    
    def set_exposure(self, exposure_us: float) -> bool:
        """设置曝光"""
        self._exposure_us = exposure_us
        logger.debug(f"SimCamera: Exposure set to {exposure_us} μs")
        return True
    
    def set_gain(self, gain: float) -> bool:
        """设置增益"""
        self._gain = gain
        logger.debug(f"SimCamera: Gain set to {gain} dB")
        return True
    
    def set_roi(self, x: int, y: int, width: int, height: int) -> bool:
        """设置ROI"""
        self._width = width
        self._height = height
        logger.debug(f"SimCamera: ROI set to ({x}, {y}, {width}, {height})")
        return True
    
    def set_trigger_mode(self, mode: TriggerMode, source: str = "Line1") -> bool:
        """设置触发模式"""
        self._trigger_mode = mode
        logger.debug(f"SimCamera: Trigger mode set to {mode.value}")
        return True
    
    def start_acquisition(self) -> bool:
        """开始采集"""
        self._is_acquiring = True
        self._state = DeviceState.ACQUIRING
        logger.debug("SimCamera: Acquisition started")
        return True
    
    def stop_acquisition(self) -> bool:
        """停止采集"""
        self._is_acquiring = False
        self._state = DeviceState.IDLE
        logger.debug("SimCamera: Acquisition stopped")
        return True
    
    def grab(self, timeout_ms: int = 5000) -> Optional[NDArray[np.uint16]]:
        """抓取一帧图像"""
        if not self._is_acquiring:
            logger.warning("SimCamera: Not in acquisition mode")
            return None
        
        # 模拟曝光时间
        time.sleep(self._exposure_us / 1000000.0)
        
        # 生成模拟图像
        image = self._generate_simulated_image()
        
        self._frame_count += 1
        logger.debug(f"SimCamera: Grabbed frame {self._frame_count}")
        
        return image
    
    def grab_sequence(
        self,
        n_frames: int,
        timeout_ms: int = 30000
    ) -> List[NDArray[np.uint16]]:
        """抓取序列图像"""
        images = []
        
        for i in range(n_frames):
            img = self.grab(timeout_ms // n_frames)
            if img is not None:
                images.append(img)
            else:
                logger.warning(f"SimCamera: Failed to grab frame {i+1}/{n_frames}")
        
        logger.info(f"SimCamera: Grabbed {len(images)}/{n_frames} frames")
        return images
    
    def _generate_simulated_image(self) -> NDArray[np.uint16]:
        """生成模拟图像
        
        Returns:
            NDArray: 12位图像数据
        """
        # 基础图像（高斯噪声）
        image = np.random.normal(2048, 200, (self._height, self._width))
        
        # 添加一些特征（模拟样品）
        center_x, center_y = self._width // 2, self._height // 2
        y, x = np.ogrid[-center_y:self._height-center_y, -center_x:self._width-center_x]
        
        # 添加圆形特征
        mask = x*x + y*y <= (self._width // 4)**2
        image[mask] += 500
        
        # 随机添加瑕疵
        if np.random.random() < self._defect_probability:
            # 添加亮点瑕疵
            defect_x = np.random.randint(0, self._width)
            defect_y = np.random.randint(0, self._height)
            defect_size = np.random.randint(10, 50)
            
            y, x = np.ogrid[-defect_y:self._height-defect_y, -defect_x:self._width-defect_x]
            defect_mask = x*x + y*y <= defect_size**2
            image[defect_mask] += 1000  # 明显的亮点
        
        # 限制到12位范围
        image = np.clip(image, 0, 4095)
        
        return image.astype(np.uint16)
    
    def get_frame_count(self) -> int:
        """获取帧计数"""
        return self._frame_count
    
    @property
    def width(self) -> int:
        """图像宽度"""
        return self._width
    
    @property
    def height(self) -> int:
        """图像高度"""
        return self._height


__all__ = ["SimCamera"]
