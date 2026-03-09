"""
自定义异常类
"""


class DAC3DError(Exception):
    """DAC-3D系统基础异常"""
    pass


class HardwareError(DAC3DError):
    """硬件错误"""
    pass


class CommunicationError(DAC3DError):
    """通信错误"""
    pass


class ConfigurationError(DAC3DError):
    """配置错误"""
    pass


class ScanError(DAC3DError):
    """扫描错误"""
    pass


class CalibrationError(DAC3DError):
    """标定错误"""
    pass


class StateTransitionError(DAC3DError):
    """状态转换错误"""
    pass


__all__ = [
    "DAC3DError",
    "HardwareError",
    "CommunicationError",
    "ConfigurationError",
    "ScanError",
    "CalibrationError",
    "StateTransitionError",
]
