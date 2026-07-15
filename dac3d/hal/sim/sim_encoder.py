"""
编码器/位置源模拟驱动 —— 软件在环 + 单元测试

`SimEncoderSource` 实现厂商无关的 `IEncoderSource` 接口, 用于在无硬件时验证
"运动↔视觉"结合边界的行为(位置读取、清零、位置同步输出 PSO)。
"""

import time
import logging
from typing import Dict, Any, Optional, List, Sequence

from dac3d.hal.interfaces import (
    IEncoderSource,
    DeviceState,
    TriggerConfig,
    EncoderCapabilities,
    EncoderReading,
    EncoderInterface,
)


logger = logging.getLogger(__name__)


class SimEncoderSource(IEncoderSource):
    """编码器位置源模拟器

    维护一份可被外部推进的模拟位置(μm), 并模拟位置同步输出(PSO)的触发计数。
    默认声明为厂商无关的正交差分路径, 支持硬件 PSO, 便于在 SIL 下验证纳秒级触发流程。
    """

    def __init__(
        self,
        device_id: str = "sim_encoder",
        resolution_nm: float = 1.0,
        axes: Sequence[str] = ("x", "y", "z"),
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(device_id, config)
        self._resolution_nm = resolution_nm
        self._axes: List[str] = [a.lower() for a in axes]
        self._position_um: Dict[str, float] = {a: 0.0 for a in self._axes}

        self._pso_config: Optional[TriggerConfig] = None
        self._armed = False
        self._frame_count = 0

        logger.info(
            f"SimEncoderSource initialized: axes={self._axes}, "
            f"resolution={resolution_nm}nm/count"
        )

    # ---- IDevice ----

    def connect(self) -> bool:
        self._state = DeviceState.CONNECTED
        return True

    def disconnect(self) -> bool:
        self._armed = False
        self._state = DeviceState.DISCONNECTED
        return True

    def reset(self) -> bool:
        self._armed = False
        self._frame_count = 0
        self.zero()
        self._state = DeviceState.IDLE
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "device_id": self._device_id,
            "type": "Simulated Encoder Source",
            "capabilities": self.get_capabilities().to_dict(),
            "frame_count": self._frame_count,
            "state": self._state.name,
        }

    # ---- IEncoderSource ----

    def get_capabilities(self) -> EncoderCapabilities:
        return EncoderCapabilities(
            axes=list(self._axes),
            resolution_nm=self._resolution_nm,
            interface=EncoderInterface.QUADRATURE_DIFFERENTIAL,
            supports_hardware_pso=True,
            vendor="generic",
            model="sim",
        )

    def read_position(self, axis: str) -> float:
        return self._position_um.get(axis.lower(), 0.0)

    def read_counts(self, axis: str) -> int:
        return int(round(self.read_position(axis) * 1000.0 / self._resolution_nm))

    def read_all(self) -> EncoderReading:
        counts: Dict[str, int] = {}
        position: Dict[str, float] = {}
        for ax in self._axes:
            position[ax] = self._position_um[ax]
            counts[ax] = int(round(position[ax] * 1000.0 / self._resolution_nm))
        return EncoderReading(
            counts=counts,
            position_um=position,
            timestamp_ns=time.monotonic_ns(),
        )

    def zero(self, axis: Optional[str] = None) -> bool:
        axes = self._axes if axis is None else [axis.lower()]
        for ax in axes:
            if ax in self._position_um:
                self._position_um[ax] = 0.0
        return True

    def configure_pso(self, config: TriggerConfig) -> bool:
        if not config.validate():
            self._error_msg = "invalid PSO config"
            logger.error(self._error_msg)
            return False
        self._pso_config = config
        self._frame_count = 0
        self._state = DeviceState.READY
        logger.info(
            f"SimEncoderSource: PSO configured axis={config.axis} "
            f"start={config.start_pos} end={config.end_pos} interval={config.interval}"
        )
        return True

    def arm_pso(self) -> bool:
        if not self._pso_config:
            logger.error("SimEncoderSource: PSO not configured")
            return False
        self._armed = True
        self._state = DeviceState.BUSY
        return True

    def disarm_pso(self) -> bool:
        self._armed = False
        self._state = DeviceState.IDLE
        return True

    @property
    def supports_hardware_pso(self) -> bool:
        return True

    # ---- 仿真辅助 ----

    def set_position(self, axis: str, position_um: float) -> int:
        """设置模拟位置并返回本次新增的 PSO 触发次数

        Args:
            axis: 轴
            position_um: 绝对位置(μm)

        Returns:
            int: 本次移动新增的触发次数(仅当已武装且监控轴匹配)
        """
        axis = axis.lower()
        if axis in self._position_um:
            self._position_um[axis] = position_um
        return self._update_triggers(axis)

    def advance(self, axis: str, delta_um: float) -> int:
        """相对推进模拟位置并返回本次新增触发次数"""
        axis = axis.lower()
        if axis in self._position_um:
            self._position_um[axis] += delta_um
        return self._update_triggers(axis)

    def _update_triggers(self, moved_axis: str) -> int:
        if not (self._armed and self._pso_config):
            return 0
        cfg = self._pso_config
        if moved_axis != cfg.axis.lower():
            return 0
        pos = self._position_um[moved_axis]
        if pos < cfg.start_pos or pos > cfg.end_pos:
            return 0
        expected = int((pos - cfg.start_pos) / cfg.interval) + 1
        if expected > self._frame_count:
            new = expected - self._frame_count
            self._frame_count = expected
            return new
        return 0

    def get_frame_count(self) -> int:
        """获取 PSO 触发帧计数"""
        return self._frame_count


__all__ = ["SimEncoderSource"]
