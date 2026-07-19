"""
切片推理(tiling)核心 —— 性能与小目标检测的关键

单视场 2048×2048、瑕疵仅约 7px：整图缩到 640 会丢瑕疵，必须**原分辨率裁剪**成
带 overlap 的切片，逐片推理，再把跨片框做全局 NMS 合并回全图坐标。
"""

import logging
from typing import List, Tuple, Iterator

import numpy as np
from numpy.typing import NDArray

from dac3d.services.ai_detection.interface import DefectCandidate

logger = logging.getLogger(__name__)


class Tiler:
    """原分辨率切片器 + 跨片全局 NMS 合并"""

    def __init__(self, tile_size: int = 640, overlap: float = 0.15):
        """初始化

        Args:
            tile_size: 切片边长(像素)
            overlap: 相邻切片重叠比例(0-1)，避免瑕疵被切边漏检
        """
        if not (0.0 <= overlap < 1.0):
            raise ValueError("overlap 必须在 [0,1)")
        self._tile = tile_size
        self._overlap = overlap
        self._stride = max(1, int(round(tile_size * (1.0 - overlap))))

    def tile_origins(self, width: int, height: int) -> List[Tuple[int, int]]:
        """计算所有切片左上角坐标(覆盖到边缘)"""
        def axis(total: int) -> List[int]:
            if total <= self._tile:
                return [0]
            xs = list(range(0, total - self._tile + 1, self._stride))
            if xs[-1] != total - self._tile:
                xs.append(total - self._tile)  # 补最后一片贴到边缘
            return xs
        return [(x, y) for y in axis(height) for x in axis(width)]

    def n_tiles(self, width: int, height: int) -> int:
        return len(self.tile_origins(width, height))

    def iter_tiles(
        self, image: NDArray
    ) -> Iterator[Tuple[int, int, NDArray]]:
        """产出 (x0, y0, 切片图)，切片为原分辨率裁剪，不缩放"""
        h, w = image.shape[:2]
        for x0, y0 in self.tile_origins(w, h):
            yield x0, y0, image[y0:y0 + self._tile, x0:x0 + self._tile]

    @staticmethod
    def merge(
        candidates: List[DefectCandidate], iou_thresh: float = 0.5
    ) -> List[DefectCandidate]:
        """跨片全局 NMS：合并重叠区重复检出，保留每簇最高置信度

        按类别分别 NMS（不同类的框不互相抑制）。
        """
        if not candidates:
            return []

        kept: List[DefectCandidate] = []
        by_cls: dict = {}
        for c in candidates:
            by_cls.setdefault(c.cls, []).append(c)

        for cls_cands in by_cls.values():
            cls_cands = sorted(cls_cands, key=lambda c: c.confidence, reverse=True)
            picked: List[DefectCandidate] = []
            for cand in cls_cands:
                if all(Tiler._iou(cand.bbox, p.bbox) < iou_thresh for p in picked):
                    picked.append(cand)
            kept.extend(picked)
        return kept

    @staticmethod
    def _iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        if inter == 0:
            return 0.0
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        return inter / float(area_a + area_b - inter)


__all__ = ["Tiler"]
