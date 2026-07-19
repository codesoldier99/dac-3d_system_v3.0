"""
YOLO + TensorRT 生产检测后端（Windows + NVIDIA GPU）—— 骨架

热路径(engine 推理)依赖 tensorrt/pycuda/torch，仅在生产机可用；因此这些导入**延迟到
运行时**，保证本模块在无 GPU 的开发/仿真环境也能被导入(架构可测)。生产建议将热路径
转 C++(TensorRT C++ API)；本骨架用于训练/验证/算法迭代与流水线打通。

流水线三段异步 + CUDA Streams 重叠 H2D/kernel/D2H；预处理上 GPU；切片成 batch 喂 engine。
"""

import time
import logging
from typing import Optional, List

import numpy as np
from numpy.typing import NDArray

from dac3d.services.ai_detection.interface import (
    IDefectDetector,
    DefectResult,
    DefectCandidate,
    DetectorConfig,
)
from dac3d.services.ai_detection.tiling import Tiler
from dac3d.services.ai_detection.fusion import HeightFusion

logger = logging.getLogger(__name__)


class YoloTrtDetector(IDefectDetector):
    """YOLO11 + TensorRT INT8 引擎推理（生产）"""

    def __init__(
        self,
        engine_path: str,
        config: Optional[DetectorConfig] = None,
        classifier_engine_path: Optional[str] = None,
    ):
        """初始化

        Args:
            engine_path: 一级 YOLO 的 TensorRT engine(.engine) 路径
            config: 检测配置(配方)
            classifier_engine_path: 二级轻量分类器 engine(可选，"去伪存真")
        """
        self._engine_path = engine_path
        self._classifier_path = classifier_engine_path
        self._cfg = config or DetectorConfig()
        self._tiler = Tiler(self._cfg.tile_size, self._cfg.overlap)
        self._fusion = HeightFusion(self._cfg)
        self._engine = None  # 延迟加载
        logger.info(f"YoloTrtDetector configured (engine={engine_path})")

    def warmup(self) -> None:
        """加载 engine 并跑一次空推理稳定时延"""
        self._ensure_engine()
        dummy = np.zeros((self._cfg.tile_size, self._cfg.tile_size), dtype=np.uint16)
        self._infer_batch([dummy])

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return
        try:
            import tensorrt as trt  # noqa: F401  (生产机才有)
        except ImportError as e:  # pragma: no cover - 无 GPU 环境
            raise RuntimeError(
                "TensorRT 未安装：YoloTrtDetector 需在带 NVIDIA GPU 的生产机运行。"
                "开发/仿真请使用 SimDefectDetector。"
            ) from e
        # TODO(生产): 反序列化 engine、分配 pinned/device buffers、建 CUDA streams
        raise NotImplementedError(
            "engine 加载为生产骨架：需按目标机 TensorRT 版本实现 deserialize + buffer 分配。"
        )

    def detect(
        self,
        image: NDArray[np.uint16],
        z_map: Optional[NDArray[np.float32]] = None,
    ) -> DefectResult:
        t0 = time.perf_counter()
        self._ensure_engine()

        # 1) 原分辨率切片成 batch
        tiles, origins = [], []
        for x0, y0, tile in self._tiler.iter_tiles(image):
            tiles.append(tile)
            origins.append((x0, y0))

        # 2) 分批 TensorRT 推理(INT8)，得到每片候选，映射回全图坐标
        raw: List[DefectCandidate] = []
        for det, (x0, y0) in zip(self._infer_batch(tiles), origins):
            raw.extend(self._to_global(det, x0, y0))

        # 3) 跨片全局 NMS 合并
        merged = Tiler.merge(raw, self._cfg.iou_nms)

        # 4) 3D 高度融合去伪(灰尘) + 可选二级分类器
        self._fusion.apply(merged, z_map)
        if self._classifier_path:
            self._second_stage(image, merged)

        infer_ms = (time.perf_counter() - t0) * 1000.0
        kept = [c for c in merged if c.verified]
        return DefectResult(
            has_defect=len(kept) > 0,
            candidates=merged,
            n_tiles=len(tiles),
            infer_ms=infer_ms,
        )

    # ---- 生产骨架：以下方法在目标机实现 ----

    def _infer_batch(self, tiles: List[NDArray]):  # pragma: no cover
        """对一批切片做 TensorRT 推理，返回每片的原始检测。生产实现。"""
        raise NotImplementedError("生产骨架：实现 GPU 预处理 + engine 推理 + 解码")

    def _to_global(self, det, x0: int, y0: int) -> List[DefectCandidate]:  # pragma: no cover
        """把切片内检测框坐标 + 类别 + 置信度映射为全图 DefectCandidate。"""
        raise NotImplementedError("生产骨架：按 engine 输出格式解码为 DefectCandidate")

    def _second_stage(self, image: NDArray, candidates: List[DefectCandidate]) -> None:  # pragma: no cover
        """二级轻量分类器：crop 候选框过 ResNet18/MobileNet 去伪存真。"""
        raise NotImplementedError("生产骨架：实现二级分类器 crop 推理")


__all__ = ["YoloTrtDetector"]
