"""
AI 瑕疵检测服务 —— 可换检测后端(传统CV / YOLO-TensorRT / 仿真)

对应指标 (5)(6)(8)：表面颗粒/麻点/划痕/崩边；敏感性≥99%、特异性≥90%。
方案见 docs/dac3d-ai-defect-inspection.md。
"""

from dac3d.services.ai_detection.interface import (
    IDefectDetector,
    DefectResult,
    DefectCandidate,
    DefectClass,
    DetectorConfig,
)
from dac3d.services.ai_detection.tiling import Tiler
from dac3d.services.ai_detection.fusion import HeightFusion
from dac3d.services.ai_detection.sim_detector import SimDefectDetector
from dac3d.services.ai_detection.yolo_trt_detector import YoloTrtDetector

__all__ = [
    "IDefectDetector",
    "DefectResult",
    "DefectCandidate",
    "DefectClass",
    "DetectorConfig",
    "Tiler",
    "HeightFusion",
    "SimDefectDetector",
    "YoloTrtDetector",
]
