"""
AI 瑕疵检测单元测试

验证:
1. 切片(tiling)数量与吞吐相关的几何(2048@640/0.15 → 16 片)
2. 跨片 NMS 合并
3. SimDefectDetector 端到端流水线
4. 3D 高度融合(核心): 灰尘(+Z 凸起)剔除、麻点(−Z 凹陷)保留 —— 保特异性
"""

import numpy as np
import pytest

from dac3d.services.ai_detection.interface import (
    IDefectDetector,
    DefectCandidate,
    DefectClass,
    DetectorConfig,
)
from dac3d.services.ai_detection.tiling import Tiler
from dac3d.services.ai_detection.fusion import HeightFusion
from dac3d.services.ai_detection.sim_detector import SimDefectDetector


class TestTiler:
    def test_tile_count_2048(self):
        """2048×2048、640 切片、15% overlap → 4×4 = 16 片（方案里的吞吐基数）"""
        tiler = Tiler(tile_size=640, overlap=0.15)
        assert tiler.n_tiles(2048, 2048) == 16

    def test_edge_coverage(self):
        """最后一片贴到边缘，保证全覆盖"""
        tiler = Tiler(tile_size=640, overlap=0.15)
        origins = tiler.tile_origins(2048, 2048)
        xs = sorted({x for x, _ in origins})
        assert xs[0] == 0
        assert xs[-1] == 2048 - 640  # 最后一片右边缘对齐

    def test_small_image_single_tile(self):
        tiler = Tiler(tile_size=640, overlap=0.15)
        assert tiler.n_tiles(500, 500) == 1

    def test_merge_dedup_overlap(self):
        """重叠区同类重复框被 NMS 合并为一个(留高置信度)"""
        a = DefectCandidate(DefectClass.PIT, (100, 100, 120, 120), 0.9)
        b = DefectCandidate(DefectClass.PIT, (102, 101, 122, 121), 0.6)  # 高度重叠
        merged = Tiler.merge([a, b], iou_thresh=0.5)
        assert len(merged) == 1
        assert merged[0].confidence == 0.9

    def test_merge_keeps_different_class(self):
        a = DefectCandidate(DefectClass.PIT, (100, 100, 120, 120), 0.9)
        b = DefectCandidate(DefectClass.PARTICLE, (100, 100, 120, 120), 0.9)
        assert len(Tiler.merge([a, b], 0.5)) == 2


class TestSimDetector:
    def test_is_detector(self):
        assert isinstance(SimDefectDetector(), IDefectDetector)

    def test_detects_bright_spot(self):
        """注入一个亮斑，应被检出"""
        img = np.full((640, 640), 1000, dtype=np.uint16)
        img[300:310, 300:310] = 8000  # 亮斑
        res = SimDefectDetector().detect(img)
        assert res.has_defect
        assert res.n_tiles == 1
        assert any(c.cls == DefectClass.PARTICLE for c in res.candidates)

    def test_clean_image_no_defect(self):
        img = np.full((640, 640), 1000, dtype=np.uint16)
        res = SimDefectDetector().detect(img)
        assert not res.has_defect


class TestHeightFusion:
    """3D 高度融合 —— 特异性核心"""

    def _cfg(self):
        return DetectorConfig(dust_reject_height_nm=50.0)

    def test_dust_rejected(self):
        """局部凸起(+300nm)于表面之上 → 判为灰尘剔除"""
        z = np.zeros((200, 200), dtype=np.float32)  # 表面基准 0
        z[90:110, 90:110] = 300.0  # 框内凸起(灰尘)
        cand = DefectCandidate(DefectClass.PARTICLE, (90, 90, 110, 110), 0.8)
        HeightFusion(self._cfg()).apply([cand], z)
        assert cand.verified is False
        assert "dust" in cand.reject_reason
        assert cand.height_nm > 50

    def test_pit_kept(self):
        """局部凹陷(−300nm)低于表面 → 麻点，保留"""
        z = np.zeros((200, 200), dtype=np.float32)
        z[90:110, 90:110] = -300.0  # 框内凹陷(麻点)
        cand = DefectCandidate(DefectClass.PIT, (90, 90, 110, 110), 0.8)
        HeightFusion(self._cfg()).apply([cand], z)
        assert cand.verified is True
        assert cand.height_nm < 0

    def test_chip_by_zstd(self):
        """崩边: 框内深度突变(方差大) → 保留"""
        z = np.zeros((200, 200), dtype=np.float32)
        z[90:110, 100:110] = -500.0  # 半边缺失，制造深度突变
        cfg = DetectorConfig(chip_zstd_nm=100.0)
        cand = DefectCandidate(DefectClass.CHIP, (90, 90, 110, 110), 0.5)
        HeightFusion(cfg).apply([cand], z)
        assert cand.verified is True

    def test_no_zmap_keeps_all(self):
        """无 Z 图时不做融合，全部保留"""
        cand = DefectCandidate(DefectClass.PARTICLE, (90, 90, 110, 110), 0.8)
        HeightFusion(self._cfg()).apply([cand], None)
        assert cand.verified is True

    def test_end_to_end_dust_rejection(self):
        """端到端: 亮斑 + 对应位置为凸起 → 检出但被 3D 判为灰尘剔除"""
        img = np.full((640, 640), 1000, dtype=np.uint16)
        img[300:312, 300:312] = 8000
        z = np.zeros((640, 640), dtype=np.float32)
        z[300:312, 300:312] = 400.0  # 凸起 → 灰尘
        res = SimDefectDetector(DetectorConfig(dust_reject_height_nm=50.0)).detect(img, z)
        assert len(res.candidates) >= 1
        assert len(res.kept()) == 0  # 全被 3D 去伪剔除
        assert not res.has_defect


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
