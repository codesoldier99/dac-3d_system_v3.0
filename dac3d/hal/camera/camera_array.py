"""
相机阵列管理器

用于管理多个相机的同步采集
"""

import logging
from typing import Dict, List, Optional
import numpy as np
from numpy.typing import NDArray
from concurrent.futures import ThreadPoolExecutor, as_completed

from dac3d.hal.interfaces import ICamera, DeviceState, TriggerMode


logger = logging.getLogger(__name__)


class CameraArray:
    """相机阵列
    
    管理多个相机的同步操作
    """
    
    def __init__(self, cameras: List[ICamera]):
        """初始化
        
        Args:
            cameras: 相机列表
        """
        self._cameras = cameras
        self._n_cameras = len(cameras)
        
        logger.info(f"CameraArray initialized with {self._n_cameras} cameras")
    
    def connect_all(self) -> bool:
        """连接所有相机"""
        results = []
        for cam in self._cameras:
            result = cam.connect()
            results.append(result)
            if result:
                logger.info(f"Camera {cam.device_id} connected")
            else:
                logger.error(f"Camera {cam.device_id} connection failed")
        
        return all(results)
    
    def disconnect_all(self) -> bool:
        """断开所有相机"""
        for cam in self._cameras:
            cam.disconnect()
        return True
    
    def set_trigger_mode_all(self, mode: TriggerMode, source: str = "Line1") -> bool:
        """设置所有相机触发模式"""
        results = [cam.set_trigger_mode(mode, source) for cam in self._cameras]
        return all(results)
    
    def start_acquisition_all(self) -> bool:
        """启动所有相机采集"""
        results = [cam.start_acquisition() for cam in self._cameras]
        return all(results)
    
    def stop_acquisition_all(self) -> bool:
        """停止所有相机采集"""
        results = [cam.stop_acquisition() for cam in self._cameras]
        return all(results)
    
    def grab_all(self, timeout_ms: int = 5000) -> Dict[str, NDArray]:
        """同时抓取所有相机图像
        
        Returns:
            Dict: {camera_id: image}
        """
        images = {}
        
        # 使用线程池并行抓取
        with ThreadPoolExecutor(max_workers=self._n_cameras) as executor:
            futures = {
                executor.submit(cam.grab, timeout_ms): cam.device_id 
                for cam in self._cameras
            }
            
            for future in as_completed(futures):
                cam_id = futures[future]
                try:
                    img = future.result()
                    if img is not None:
                        images[cam_id] = img
                except Exception as e:
                    logger.error(f"Camera {cam_id} grab failed: {e}")
        
        return images
    
    def grab_sequence_all(
        self,
        n_frames: int,
        timeout_ms: int = 30000
    ) -> Dict[str, List[NDArray]]:
        """同时抓取所有相机的序列图像
        
        Returns:
            Dict: {camera_id: [images]}
        """
        sequences = {}
        
        # 并行抓取
        with ThreadPoolExecutor(max_workers=self._n_cameras) as executor:
            futures = {
                executor.submit(cam.grab_sequence, n_frames, timeout_ms): cam.device_id
                for cam in self._cameras
            }
            
            for future in as_completed(futures):
                cam_id = futures[future]
                try:
                    imgs = future.result()
                    sequences[cam_id] = imgs
                    logger.info(f"Camera {cam_id} captured {len(imgs)} frames")
                except Exception as e:
                    logger.error(f"Camera {cam_id} sequence failed: {e}")
                    sequences[cam_id] = []
        
        return sequences
    
    @property
    def cameras(self) -> List[ICamera]:
        """获取相机列表"""
        return self._cameras
    
    def get_camera(self, index: int) -> Optional[ICamera]:
        """获取指定相机"""
        if 0 <= index < self._n_cameras:
            return self._cameras[index]
        return None


__all__ = ["CameraArray"]
