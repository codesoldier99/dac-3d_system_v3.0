"""
3D 高度融合 —— 本方案的特异性核心（把三维闪测变成"去伪"武器）

原理：真瑕疵与灰尘在 Z 高度图上符号相反。
- 麻点/划痕：材料缺失 → 低于局部表面（−Z 凹陷）
- 崩边：边缘深度突变 → 框内 Z 方差大
- 灰尘/污渍：浮于表面之上（+Z 凸起）、无嵌入深度 → 剔除以保特异性(≥90%)

这是纯 2D 竞品做不到的物理判据，直接用三维闪测(指标3/4)的差异化解决灰尘误报。
"""

import logging
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from dac3d.services.ai_detection.interface import (
    DefectCandidate,
    DefectClass,
    DetectorConfig,
)

logger = logging.getLogger(__name__)


class HeightFusion:
    """用 Z 高度图对候选框做物理校验（去伪 + 补真）"""

    def __init__(self, config: DetectorConfig):
        self._cfg = config

    def apply(
        self,
        candidates: List[DefectCandidate],
        z_map: Optional[NDArray[np.float32]],
    ) -> List[DefectCandidate]:
        """对每个候选框做 Z 高度校验，原地更新 height_nm/verified/reject_reason

        Args:
            candidates: 一级检出候选
            z_map: 同视场 Z 高度图(nm)。为 None 时不做融合(全部保留)。

        Returns:
            同一列表(已更新校验结果)
        """
        if z_map is None or not self._cfg.use_height_fusion:
            return candidates

        for c in candidates:
            self._verify_one(c, z_map)
        return candidates

    def _verify_one(self, c: DefectCandidate, z_map: NDArray[np.float32]) -> None:
        x1, y1, x2, y2 = c.bbox
        h, w = z_map.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return

        inside = z_map[y1:y2, x1:x2]
        baseline = self._ring_baseline(z_map, x1, y1, x2, y2)
        delta = float(np.median(inside)) - baseline  # 相对局部表面高度(nm)
        c.height_nm = delta

        # 崩边：看框内深度突变(方差)，是硬信号 → 保留
        if c.cls == DefectClass.CHIP:
            if float(np.std(inside)) >= self._cfg.chip_zstd_nm:
                c.verified = True
            return

        # 灰尘去伪：显著凸起于表面之上 → 判为表面污染，剔除以保特异性
        if delta > self._cfg.dust_reject_height_nm:
            c.verified = False
            c.reject_reason = f"dust:+{delta:.0f}nm"
            return

        # 凹陷(负高度)= 麻点/划痕典型签名 → 保留(真瑕疵)
        c.verified = True

    @staticmethod
    def _ring_baseline(
        z_map: NDArray[np.float32], x1: int, y1: int, x2: int, y2: int
    ) -> float:
        """用候选框外围一圈的中位数估计局部表面基准高度"""
        h, w = z_map.shape[:2]
        m = max(4, (x2 - x1) // 2)  # 外扩边距
        rx1, ry1 = max(0, x1 - m), max(0, y1 - m)
        rx2, ry2 = min(w, x2 + m), min(h, y2 + m)
        ring = z_map[ry1:ry2, rx1:rx2].astype(np.float64).copy()
        # 挖掉中心框，只留四周表面
        ring[y1 - ry1:y2 - ry1, x1 - rx1:x2 - rx1] = np.nan
        vals = ring[~np.isnan(ring)]
        return float(np.median(vals)) if vals.size else 0.0


__all__ = ["HeightFusion"]
