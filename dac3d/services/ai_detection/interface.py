"""
AI 瑕疵检测 —— 可换检测后端的统一接口

延续本项目"接口+实现分离、配方驱动、设备无关"的架构底线：检测后端(传统CV /
YOLO-TensorRT / 仿真)只依赖本接口，配方选择切换，换后端不改上层。

对应指标 (5)(6)(8)：表面颗粒/麻点/划痕/崩边；敏感性≥99%、特异性≥90%。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Tuple

import numpy as np
from numpy.typing import NDArray


class DefectClass(Enum):
    """瑕疵类别（对应指标 5/6/8）"""
    PARTICLE = "颗粒"
    PIT = "麻点"
    SCRATCH = "划痕"
    CHIP = "崩边"


@dataclass
class DefectCandidate:
    """一个候选瑕疵（一级检出，可能尚未经 3D/二级校验）"""
    cls: DefectClass
    bbox: Tuple[int, int, int, int]  # 全图像素坐标 (x1, y1, x2, y2)
    confidence: float
    source: str = "yolo"  # yolo / traditional / sim
    # 经 3D 高度融合后填充：
    height_nm: Optional[float] = None  # 相对局部表面高度：负=凹陷(真瑕疵) 正=凸起(疑灰尘)
    verified: bool = True  # 经 3D/二级校验后是否保留
    reject_reason: str = ""  # 被剔除时的原因（如 "dust:+height"）


@dataclass
class DefectResult:
    """一次检测的完整结果"""
    has_defect: bool
    candidates: List[DefectCandidate] = field(default_factory=list)
    n_tiles: int = 0
    infer_ms: float = 0.0

    def kept(self) -> List[DefectCandidate]:
        """经校验保留的真瑕疵"""
        return [c for c in self.candidates if c.verified]

    def rejected(self) -> List[DefectCandidate]:
        """被 3D/二级校验剔除的（多为灰尘/伪影）"""
        return [c for c in self.candidates if not c.verified]


@dataclass
class DetectorConfig:
    """检测配置 —— 配方驱动，换零件类型只改此处

    平板 vs 小角锲角片、不同瑕疵类别的阈值都在这里，不改代码。
    """
    # 切片(tiling)：瑕疵仅约 7px，必须原分辨率裁剪，不缩放
    tile_size: int = 640
    overlap: float = 0.15
    # 一级 YOLO：低阈"宁可错杀"保敏感性；按类别分设
    conf_by_class: Dict[str, float] = field(default_factory=lambda: {
        DefectClass.PARTICLE.value: 0.20,
        DefectClass.PIT.value: 0.20,
        DefectClass.SCRATCH.value: 0.25,
        DefectClass.CHIP.value: 0.15,
    })
    iou_nms: float = 0.5  # 跨片合并的 NMS 阈值
    # 3D 高度融合（本方案特异性核心）
    use_height_fusion: bool = True
    dust_reject_height_nm: float = 50.0  # 局部凸起且高于此值 → 疑似灰尘剔除
    chip_zstd_nm: float = 100.0  # 崩边判据：框内 Z 方差(标准差)高于此值视为深度突变

    def conf_threshold(self, cls: DefectClass) -> float:
        return self.conf_by_class.get(cls.value, 0.25)


class IDefectDetector(ABC):
    """可换瑕疵检测后端的统一接口"""

    @abstractmethod
    def warmup(self) -> None:
        """预热（加载模型/engine、跑一次空推理稳定时延）"""
        pass

    @abstractmethod
    def detect(
        self,
        image: NDArray[np.uint16],
        z_map: Optional[NDArray[np.float32]] = None,
    ) -> DefectResult:
        """检测单视场图像中的瑕疵

        Args:
            image: 单视场 2D 图（如 2048×2048）
            z_map: 同视场 Z 高度图(nm)，来自三维闪测；提供则启用 3D 高度融合去伪

        Returns:
            DefectResult：候选 + 校验结果 + 计时
        """
        pass


__all__ = [
    "DefectClass",
    "DefectCandidate",
    "DefectResult",
    "DetectorConfig",
    "IDefectDetector",
]
