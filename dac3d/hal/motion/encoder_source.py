"""
编码器/位置源驱动 —— 厂商无关的"运动↔视觉"结合边界

本模块提供 `IEncoderSource` 的具体实现, 落实产品战略"增强所有运动卡厂家"
(见 docs/dac3d-product-strategy.md 第 6.1 节)。

两类实现:
- `FpgaQuadratureEncoderSource`: **厂商无关的通用路径**。只要运动卡输出标准正交
  编码器信号(A/B/Z 差分)接入 FPGA, 即可拿到纳秒级位置触发, 不感知运动卡品牌。
  这是推荐的生产路径, 也是"不绑死某一家运动卡"的结构性保证。
- `ZMotionCardEncoderSource`: 具体厂商适配示例(经运动卡总线读位置)。展示"接入一家
  具体厂商"只需写一个本接口驱动, 而核心与 FPGA 逻辑不变。

新增一家运动卡厂商(固高/雷赛/EtherCAT...) = 新增一个本接口驱动 + 一份配方。
"""

import time
import logging
from typing import Dict, Any, Optional, List, Sequence

from dac3d.hal.interfaces import (
    IEncoderSource,
    IFPGA,
    IStage,
    DeviceState,
    TriggerConfig,
    EncoderCapabilities,
    EncoderReading,
    EncoderInterface,
)


logger = logging.getLogger(__name__)


class FpgaQuadratureEncoderSource(IEncoderSource):
    """厂商无关的正交编码器位置源(编码器差分直入 FPGA)

    只依赖"运动卡输出标准正交编码器信号"这一前提, 与运动卡品牌无关。位置读取与
    位置同步输出(PSO)全部由 FPGA 完成, 因此可拿到纳秒级时序。任何厂商的运动卡
    (ZMotion/固高/雷赛/伺服驱动器...)只要把编码器 A/B/Z 差分接到 FPGA 即可使用。
    """

    def __init__(
        self,
        fpga: IFPGA,
        device_id: str = "encoder_fpga_quad",
        resolution_nm: float = 1.0,
        axes: Sequence[str] = ("x", "y", "z"),
        vendor: str = "generic",
        model: str = "generic",
        config: Optional[Dict[str, Any]] = None,
    ):
        """初始化

        Args:
            fpga: 已接入编码器信号的 FPGA 控制器(IFPGA 实现)
            device_id: 设备ID
            resolution_nm: 每计数对应的物理位移(nm)
            axes: 支持的轴
            vendor/model: 仅作信息标注; 通用路径下与品牌解耦
            config: 额外配置
        """
        super().__init__(device_id, config)
        self._fpga = fpga
        self._resolution_nm = resolution_nm
        self._axes: List[str] = [a.lower() for a in axes]
        self._vendor = vendor
        self._model = model
        self._armed = False
        logger.info(
            f"FpgaQuadratureEncoderSource initialized: axes={self._axes}, "
            f"resolution={resolution_nm}nm/count (vendor-neutral path)"
        )

    # ---- IDevice ----

    def connect(self) -> bool:
        """连接(依附于底层 FPGA 的连接状态)"""
        if not self._fpga.is_connected:
            if not self._fpga.connect():
                self._error_msg = "underlying FPGA connect failed"
                self._state = DeviceState.ERROR
                return False
        self._state = DeviceState.CONNECTED
        return True

    def disconnect(self) -> bool:
        """断开(不代持 FPGA 生命周期, 仅解除武装)"""
        self.disarm_pso()
        self._state = DeviceState.DISCONNECTED
        return True

    def reset(self) -> bool:
        """复位: 解除武装并清零"""
        self.disarm_pso()
        self.zero()
        self._state = DeviceState.IDLE
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "device_id": self._device_id,
            "type": "FPGA Quadrature Encoder Source",
            "path": "vendor-neutral",
            "capabilities": self.get_capabilities().to_dict(),
            "state": self._state.name,
        }

    # ---- IEncoderSource ----

    def get_capabilities(self) -> EncoderCapabilities:
        return EncoderCapabilities(
            axes=list(self._axes),
            resolution_nm=self._resolution_nm,
            interface=EncoderInterface.QUADRATURE_DIFFERENTIAL,
            supports_hardware_pso=True,
            vendor=self._vendor,
            model=self._model,
        )

    def read_position(self, axis: str) -> float:
        """物理位置(μm) —— 由 FPGA 编码器寄存器提供"""
        return self._fpga.get_encoder_position(axis.lower())

    def read_counts(self, axis: str) -> int:
        """原始计数 = 位置(μm) × 1000 / 分辨率(nm)"""
        pos_um = self.read_position(axis)
        return int(round(pos_um * 1000.0 / self._resolution_nm))

    def read_all(self) -> EncoderReading:
        counts: Dict[str, int] = {}
        position: Dict[str, float] = {}
        for ax in self._axes:
            position[ax] = self.read_position(ax)
            counts[ax] = int(round(position[ax] * 1000.0 / self._resolution_nm))
        return EncoderReading(
            counts=counts,
            position_um=position,
            timestamp_ns=time.monotonic_ns(),
        )

    def zero(self, axis: Optional[str] = None) -> bool:
        """清零: 通过 FPGA 复位编码器计数(真实实现依赖具体 FPGA 驱动)"""
        # 依赖底层 FPGA 的复位接口; 仿真 FPGA 通过 reset 清零编码器
        try:
            self._fpga.reset()
            return True
        except Exception as e:  # pragma: no cover - 防御性
            logger.error(f"zero encoder failed: {e}")
            return False

    def configure_pso(self, config: TriggerConfig) -> bool:
        """配置位置同步输出 —— 委托 FPGA 硬件 PSO"""
        if not config.validate():
            self._error_msg = "invalid PSO config"
            logger.error(self._error_msg)
            return False
        ok = self._fpga.configure_pso(config)
        if ok:
            self._state = DeviceState.READY
        return ok

    def arm_pso(self) -> bool:
        ok = self._fpga.start_pso()
        self._armed = ok
        if ok:
            self._state = DeviceState.BUSY
        return ok

    def disarm_pso(self) -> bool:
        ok = self._fpga.stop_pso()
        self._armed = False
        self._state = DeviceState.IDLE
        return ok

    @property
    def supports_hardware_pso(self) -> bool:
        return True


class ZMotionCardEncoderSource(IEncoderSource):
    """ZMotion 运动卡位置源(经卡读取位置)—— 具体厂商适配示例

    展示"接入一家具体运动卡厂商"的方式: 复用已有 `ZMotionStage` 驱动读取位置,
    对上层暴露统一的 `IEncoderSource` 接口。

    注意精度定位: 本驱动经运动卡总线读位置(CARD_DIGITAL), 存在软件延迟, **不**用于
    纳秒级时序。要拿到纳秒级位置触发, 应把该卡的编码器差分信号接入 FPGA, 改用
    `FpgaQuadratureEncoderSource`(厂商无关通用路径)。本类主要用于位置监视/标定/联调。
    """

    def __init__(
        self,
        stage: IStage,
        device_id: str = "encoder_zmotion",
        resolution_nm: float = 1000.0,
        axes: Sequence[str] = ("x", "y"),
        config: Optional[Dict[str, Any]] = None,
    ):
        """初始化

        Args:
            stage: 已构造的 ZMotion 运动台驱动(IStage)
            device_id: 设备ID
            resolution_nm: 每计数对应的物理位移(nm)
            axes: 支持的轴
            config: 额外配置
        """
        super().__init__(device_id, config)
        self._stage = stage
        self._resolution_nm = resolution_nm
        self._axes: List[str] = [a.lower() for a in axes]
        self._zero_offset: Dict[str, float] = {a: 0.0 for a in self._axes}
        logger.info(
            f"ZMotionCardEncoderSource initialized: axes={self._axes} "
            f"(vendor=zmotion, path=card_digital)"
        )

    # ---- IDevice ----

    def connect(self) -> bool:
        if not self._stage.is_connected:
            if not self._stage.connect():
                self._error_msg = "underlying stage connect failed"
                self._state = DeviceState.ERROR
                return False
        self._state = DeviceState.CONNECTED
        return True

    def disconnect(self) -> bool:
        self._state = DeviceState.DISCONNECTED
        return True

    def reset(self) -> bool:
        self.zero()
        self._state = DeviceState.IDLE
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "device_id": self._device_id,
            "type": "ZMotion Card Encoder Source",
            "path": "card_digital",
            "capabilities": self.get_capabilities().to_dict(),
            "state": self._state.name,
        }

    # ---- IEncoderSource ----

    def get_capabilities(self) -> EncoderCapabilities:
        return EncoderCapabilities(
            axes=list(self._axes),
            resolution_nm=self._resolution_nm,
            interface=EncoderInterface.CARD_DIGITAL,
            supports_hardware_pso=False,  # 本卡驱动绑定下未启用硬件PSO; 纳秒触发走FPGA路径
            vendor="zmotion",
            model="ZMC",
        )

    def _axis_position_um(self, axis: str) -> float:
        pos = self._stage.get_position()
        axis = axis.lower()
        raw = {"x": pos.x, "y": pos.y, "z": pos.z}.get(axis, 0.0)
        return raw - self._zero_offset.get(axis, 0.0)

    def read_position(self, axis: str) -> float:
        return self._axis_position_um(axis)

    def read_counts(self, axis: str) -> int:
        return int(round(self.read_position(axis) * 1000.0 / self._resolution_nm))

    def read_all(self) -> EncoderReading:
        counts: Dict[str, int] = {}
        position: Dict[str, float] = {}
        for ax in self._axes:
            position[ax] = self.read_position(ax)
            counts[ax] = int(round(position[ax] * 1000.0 / self._resolution_nm))
        return EncoderReading(
            counts=counts,
            position_um=position,
            timestamp_ns=time.monotonic_ns(),
        )

    def zero(self, axis: Optional[str] = None) -> bool:
        pos = self._stage.get_position()
        raw = {"x": pos.x, "y": pos.y, "z": pos.z}
        axes = self._axes if axis is None else [axis.lower()]
        for ax in axes:
            if ax in self._zero_offset:
                self._zero_offset[ax] = raw.get(ax, 0.0)
        return True

    def configure_pso(self, config: TriggerConfig) -> bool:
        """卡读取路径不提供纳秒级硬件PSO —— 引导改用 FPGA 通用路径"""
        logger.warning(
            "ZMotionCardEncoderSource 不提供硬件PSO(card_digital路径存在软件延迟); "
            "纳秒级位置触发请把编码器接入FPGA并使用 FpgaQuadratureEncoderSource"
        )
        return False

    def arm_pso(self) -> bool:
        return False

    def disarm_pso(self) -> bool:
        return True

    @property
    def supports_hardware_pso(self) -> bool:
        return False


__all__ = ["FpgaQuadratureEncoderSource", "ZMotionCardEncoderSource"]
