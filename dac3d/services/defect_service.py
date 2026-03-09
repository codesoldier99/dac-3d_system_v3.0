"""
瑕疵检测服务

实现简单的瑕疵检测算法
"""

import logging
from typing import List, Dict, Tuple
import numpy as np
from numpy.typing import NDArray
from scipy import ndimage


logger = logging.getLogger(__name__)


class DefectInfo:
    """瑕疵信息"""
    def __init__(
        self,
        defect_type: str,
        position: Tuple[float, float],
        size: float,
        intensity: float,
        confidence: float = 1.0
    ):
        self.type = defect_type
        self.position = position
        self.size = size
        self.intensity = intensity
        self.confidence = confidence


class DefectService:
    """瑕疵检测服务
    
    使用简单的图像处理算法检测瑕疵
    """
    
    def __init__(self, config: Dict = None):
        """初始化
        
        Args:
            config: 检测参数配置
        """
        self._config = config or {}
        
        # 检测阈值
        self._threshold = self._config.get("threshold", 500)
        self._min_size = self._config.get("min_size", 5)  # 最小瑕疵尺寸(像素)
        self._max_size = self._config.get("max_size", 500)  # 最大瑕疵尺寸
        
        logger.info("DefectService initialized")
    
    def detect_defects(
        self,
        image: NDArray[np.uint16]
    ) -> Tuple[bool, List[DefectInfo]]:
        """检测图像中的瑕疵
        
        Args:
            image: 输入图像
            
        Returns:
            tuple: (has_defect, defect_list)
        """
        if image is None or image.size == 0:
            return False, []
        
        defects = []
        
        try:
            # 1. 计算图像统计
            mean_val = np.mean(image)
            std_val = np.std(image)
            
            # 2. 自适应阈值
            threshold = mean_val + 3 * std_val
            
            # 3. 二值化
            binary = image > threshold
            
            # 4. 形态学处理
            binary = ndimage.binary_opening(binary, structure=np.ones((3, 3)))
            binary = ndimage.binary_closing(binary, structure=np.ones((5, 5)))
            
            # 5. 连通域分析
            labeled, num_features = ndimage.label(binary)
            
            if num_features == 0:
                return False, []
            
            # 6. 分析每个连通域
            for i in range(1, num_features + 1):
                # 提取连通域
                mask = (labeled == i)
                size = np.sum(mask)
                
                # 过滤太小或太大的区域
                if size < self._min_size or size > self._max_size:
                    continue
                
                # 计算质心
                y_coords, x_coords = np.where(mask)
                center_x = np.mean(x_coords)
                center_y = np.mean(y_coords)
                
                # 计算强度
                intensity = np.mean(image[mask])
                
                # 判断瑕疵类型
                defect_type = self._classify_defect(size, intensity, mean_val)
                
                # 创建瑕疵对象
                defect = DefectInfo(
                    defect_type=defect_type,
                    position=(float(center_x), float(center_y)),
                    size=float(np.sqrt(size)),  # 等效直径
                    intensity=float(intensity),
                    confidence=0.85
                )
                
                defects.append(defect)
                
                logger.debug(
                    f"Detected {defect_type} at ({center_x:.1f}, {center_y:.1f}), "
                    f"size={size}px, intensity={intensity:.0f}"
                )
            
            has_defect = len(defects) > 0
            
            if has_defect:
                logger.info(f"Found {len(defects)} defect(s)")
            
            return has_defect, defects
            
        except Exception as e:
            logger.error(f"Defect detection error: {e}")
            return False, []
    
    def _classify_defect(
        self,
        size: int,
        intensity: float,
        background: float
    ) -> str:
        """分类瑕疵类型
        
        Args:
            size: 瑕疵尺寸
            intensity: 瑕疵强度
            background: 背景强度
            
        Returns:
            str: 瑕疵类型
        """
        contrast = intensity - background
        
        if contrast > 1000:
            return "亮点"
        elif contrast < -500:
            return "暗点"
        elif size > 100:
            return "大面积瑕疵"
        else:
            return"异常区域"
    
    def analyze_defect_severity(self, defect: DefectInfo) -> str:
        """分析瑕疵严重程度
        
        Args:
            defect: 瑕疵信息
            
        Returns:
            str: 严重程度 (轻微/中等/严重)
        """
        if defect.size < 10:
            return "轻微"
        elif defect.size < 50:
            return "中等"
        else:
            return "严重"


__all__ = ["DefectService", "DefectInfo"]
