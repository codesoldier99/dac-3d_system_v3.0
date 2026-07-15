"""
编码器/位置源单元测试 —— 厂商无关"运动↔视觉"结合边界

验证:
1. 厂商无关接口契约(能力、位置读取、清零、PSO)
2. SimEncoderSource 的 PSO 触发计数逻辑
3. FpgaQuadratureEncoderSource 委托 FPGA 的通用路径(不绑定具体运动卡品牌)
4. ZMotionCardEncoderSource 作为具体厂商适配的行为与精度定位
"""

import pytest

from dac3d.hal.interfaces import (
    IEncoderSource,
    TriggerConfig,
    EncoderInterface,
    Position,
)
from dac3d.hal.sim.sim_encoder import SimEncoderSource
from dac3d.hal.sim.sim_fpga import SimFPGA
from dac3d.hal.motion.encoder_source import (
    FpgaQuadratureEncoderSource,
    ZMotionCardEncoderSource,
)


class TestSimEncoderSource:
    """模拟编码器源"""

    def test_is_encoder_source(self):
        enc = SimEncoderSource()
        assert isinstance(enc, IEncoderSource)

    def test_capabilities_vendor_neutral(self):
        enc = SimEncoderSource(resolution_nm=1.0)
        cap = enc.get_capabilities()
        assert cap.interface == EncoderInterface.QUADRATURE_DIFFERENTIAL
        assert cap.supports_hardware_pso is True
        assert cap.vendor == "generic"  # 厂商无关
        assert "x" in cap.axes

    def test_position_and_counts(self):
        enc = SimEncoderSource(resolution_nm=1.0)
        enc.set_position("x", 100.0)  # 100 μm
        assert enc.read_position("x") == 100.0
        # 100 μm @ 1 nm/count = 100000 counts
        assert enc.read_counts("x") == 100000

    def test_zero(self):
        enc = SimEncoderSource()
        enc.set_position("x", 50.0)
        assert enc.read_position("x") == 50.0
        enc.zero("x")
        assert enc.read_position("x") == 0.0

    def test_read_all(self):
        enc = SimEncoderSource(axes=("x", "y"))
        enc.set_position("x", 10.0)
        enc.set_position("y", 20.0)
        reading = enc.read_all()
        assert reading.position_um["x"] == 10.0
        assert reading.position_um["y"] == 20.0
        assert reading.timestamp_ns > 0

    def test_pso_trigger_counting(self):
        """PSO: 在 [0,100] 每 10μm 触发一次, 走到 50μm 应累计 6 次(0,10,..,50)"""
        enc = SimEncoderSource(resolution_nm=1.0)
        cfg = TriggerConfig(
            mode="position", axis="x",
            start_pos=0.0, end_pos=100.0, interval=10.0,
        )
        assert enc.configure_pso(cfg) is True
        assert enc.arm_pso() is True

        total = enc.set_position("x", 50.0)
        assert total == 6
        assert enc.get_frame_count() == 6

    def test_pso_requires_arm(self):
        enc = SimEncoderSource()
        cfg = TriggerConfig(mode="position", axis="x", interval=10.0)
        enc.configure_pso(cfg)
        # 未武装, 移动不产生触发
        assert enc.set_position("x", 50.0) == 0

    def test_pso_invalid_config_rejected(self):
        enc = SimEncoderSource()
        bad = TriggerConfig(mode="position", axis="x", interval=-1.0)
        assert enc.configure_pso(bad) is False


class TestFpgaQuadratureEncoderSource:
    """厂商无关的 FPGA 正交编码器源"""

    def test_vendor_neutral_path(self):
        fpga = SimFPGA()
        fpga.connect()
        enc = FpgaQuadratureEncoderSource(fpga=fpga, resolution_nm=1.0)
        cap = enc.get_capabilities()
        # 关键: 通用路径不绑定品牌, 且支持硬件 PSO
        assert cap.interface == EncoderInterface.QUADRATURE_DIFFERENTIAL
        assert cap.supports_hardware_pso is True
        assert enc.supports_hardware_pso is True

    def test_connect_follows_fpga(self):
        fpga = SimFPGA()
        enc = FpgaQuadratureEncoderSource(fpga=fpga)
        assert enc.connect() is True
        assert enc.is_connected is True

    def test_pso_delegates_to_fpga(self):
        fpga = SimFPGA()
        fpga.connect()
        enc = FpgaQuadratureEncoderSource(fpga=fpga)
        cfg = TriggerConfig(
            mode="position", axis="x",
            start_pos=0.0, end_pos=1000.0, interval=10.0,
        )
        assert enc.configure_pso(cfg) is True
        assert enc.arm_pso() is True
        # 推进底层仿真 FPGA, 位置应经编码器源读回
        fpga.simulate_motion_step(10.0)
        assert enc.read_position("x") >= 0.0


class TestZMotionCardEncoderSource:
    """具体厂商适配(经卡读位置)"""

    def _make(self):
        stage = SimStageStub()
        return ZMotionCardEncoderSource(stage=stage, axes=("x", "y")), stage

    def test_is_encoder_source(self):
        enc, _ = self._make()
        assert isinstance(enc, IEncoderSource)

    def test_capabilities_card_digital(self):
        enc, _ = self._make()
        cap = enc.get_capabilities()
        assert cap.interface == EncoderInterface.CARD_DIGITAL
        assert cap.vendor == "zmotion"
        # 卡读取路径不承诺纳秒硬件PSO
        assert cap.supports_hardware_pso is False

    def test_position_readout_and_zero(self):
        enc, stage = self._make()
        stage.pos = Position(30.0, 40.0, 0.0)
        assert enc.read_position("x") == 30.0
        enc.zero()  # 以当前位置为零点
        assert enc.read_position("x") == 0.0
        stage.pos = Position(35.0, 40.0, 0.0)
        assert enc.read_position("x") == 5.0

    def test_pso_guides_to_fpga_path(self):
        enc, _ = self._make()
        cfg = TriggerConfig(mode="position", axis="x", interval=10.0)
        # 卡读取路径明确不提供硬件PSO, 返回 False 并引导改用 FPGA 通用路径
        assert enc.configure_pso(cfg) is False
        assert enc.arm_pso() is False


class SimStageStub:
    """最小 IStage 桩: 仅提供位置读取, 供厂商适配测试使用"""

    def __init__(self):
        self.pos = Position(0.0, 0.0, 0.0)
        self._connected = True

    @property
    def is_connected(self):
        return self._connected

    def connect(self):
        self._connected = True
        return True

    def get_position(self):
        return self.pos


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
