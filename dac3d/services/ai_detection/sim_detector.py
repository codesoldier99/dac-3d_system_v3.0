"""
仿真检测后端 —— 无 GPU 可跑，用于 SIL 与单元测试

用简单阈值+连通域找亮/暗斑作为"候选"，走完整流水线(切片→合并→3D融合)，
让"厂商无关、后端可换"的架构在无硬件时可验证。生产用 YoloTrtDetector。
"""

import time
import logging
from typing import Optional

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from dac3d.services.ai_detection.interface import (
    IDefectDetector,
    DefectResult,
    DefectCandidate,
    DefectClass,
    DetectorConfig,
)
from dac3d.services.ai_detection.tiling import Tiler
from dac3d.services.ai_detection.fusion import HeightFusion

logger = logging.getLogger(__name__)


class SimDefectDetector(IDefectDetector):
    """仿真瑕疵检测器（切片 + 简单斑点检出 + 3D 高度融合）"""

    def __init__(self, config: Optional[DetectorConfig] = None):
        self._cfg = config or DetectorConfig()
        self._tiler = Tiler(self._cfg.tile_size, self._cfg.overlap)
        self._fusion = HeightFusion(self._cfg)
        logger.info("SimDefectDetector initialized")

    def warmup(self) -> None:
        _ = np.zeros((self._cfg.tile_size, self._cfg.tile_size), dtype=np.uint16)

    def detect(
        self,
        image: NDArray[np.uint16],
        z_map: Optional[NDArray[np.float32]] = None,
    ) -> DefectResult:
        t0 = time.perf_counter()
        raw = []
        n_tiles = 0
        for x0, y0, tile in self._tiler.iter_tiles(image):
            n_tiles += 1
            raw.extend(self._detect_tile(tile, x0, y0))

        merged = Tiler.merge(raw, self._cfg.iou_nms)
        self._fusion.apply(merged, z_map)  # 3D 去伪(有 z_map 时)

        infer_ms = (time.perf_counter() - t0) * 1000.0
        kept = [c for c in merged if c.verified]
        return DefectResult(
            has_defect=len(kept) > 0,
            candidates=merged,
            n_tiles=n_tiles,
            infer_ms=infer_ms,
        )

    def _detect_tile(self, tile: NDArray, x0: int, y0: int):
        """切片内简单斑点检出（模拟一级 YOLO 的候选输出）"""
        if tile.size == 0:
            return []
        mean, std = float(np.mean(tile)), float(np.std(tile))
        if std < 1e-6:
            return []
        # 亮/暗斑各取一支
        bright = tile > (mean + 3 * std)
        dark = tile < (mean - 3 * std)

        out = []
        for mask, cls in ((bright, DefectClass.PARTICLE), (dark, DefectClass.PIT)):
            labeled, n = ndimage.label(mask)
            for i in range(1, n + 1):
                ys, xs = np.where(labeled == i)
                if xs.size < 3:  # 太小的忽略
                    continue
                bx1, by1 = int(xs.min()) + x0, int(ys.min()) + y0
                bx2, by2 = int(xs.max()) + x0 + 1, int(ys.max()) + y0 + 1
                conf = min(1.0, 0.5 + xs.size / 500.0)
                if conf < self._cfg.conf_threshold(cls):
                    continue
                out.append(DefectCandidate(
                    cls=cls, bbox=(bx1, by1, bx2, by2),
                    confidence=conf, source="sim",
                ))
        return out


__all__ = ["SimDefectDetector"]
