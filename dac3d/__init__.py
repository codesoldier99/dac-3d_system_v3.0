"""
DAC-3D 产业化光学检测系统
Copyright © 2026 福特科技

核心包入口
"""

__version__ = "3.0.0"
__author__ = "福特科技研发团队"

from dac3d.hal.interfaces import (
    Position,
    ScanRegion,
    TriggerConfig,
    DeviceState,
    IDevice,
    IStage,
    ICamera,
    IDMD,
    ILight,
    IFPGA,
)

__all__ = [
    "__version__",
    "Position",
    "ScanRegion",
    "TriggerConfig",
    "DeviceState",
    "IDevice",
    "IStage",
    "ICamera",
    "IDMD",
    "ILight",
    "IFPGA",
]
