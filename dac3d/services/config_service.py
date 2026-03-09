"""
配置服务

管理系统配置参数
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator


logger = logging.getLogger(__name__)


class HardwareConfig(BaseModel):
    """硬件配置"""
    # FPGA配置
    fpga_host: str = Field(default="192.168.1.10", description="FPGA IP地址")
    fpga_port: int = Field(default=5000, description="FPGA TCP端口")
    encoder_resolution_nm: float = Field(default=1.0, description="编码器分辨率(nm)")
    
    # ZMotion配置
    zmotion_ip: str = Field(default="192.168.0.11", description="ZMotion IP")
    zmotion_x_axis: int = Field(default=0, description="X轴编号")
    zmotion_y_axis: int = Field(default=1, description="Y轴编号")
    zmotion_speed: float = Field(default=100.0, description="运动速度(mm/s)")
    
    # PI压电台配置
    pi_connection: str = Field(default="tcp", description="连接类型")
    pi_address: str = Field(default="192.168.1.20", description="PI地址")
    pi_axis: str = Field(default="1", description="PI轴名称")
    pi_range_min: float = Field(default=0.0, description="Z轴最小值(μm)")
    pi_range_max: float = Field(default=100.0, description="Z轴最大值(μm)")
    
    # Basler相机配置
    camera_serial_numbers: list = Field(default_factory=lambda: [None, None, None])
    camera_exposure_us: float = Field(default=1000.0, description="曝光时间(μs)")
    camera_gain: float = Field(default=0.0, description="增益(dB)")


class ScanConfig(BaseModel):
    """扫描配置"""
    default_step_x: float = Field(default=10.0, description="X步进(μm)")
    default_step_y: float = Field(default=10.0, description="Y步进(μm)")
    default_step_z: float = Field(default=1.0, description="Z步进(μm)")
    
    scan_velocity: float = Field(default=10.0, description="扫描速度(mm/s)")
    
    @validator('default_step_x', 'default_step_y', 'default_step_z')
    def validate_step(cls, v):
        if v <= 0:
            raise ValueError("Step must be positive")
        return v


class SystemConfig(BaseModel):
    """系统配置"""
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    
    data_dir: str = Field(default="./data", description="数据目录")
    log_level: str = Field(default="INFO", description="日志级别")


class ConfigService:
    """配置服务"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化
        
        Args:
            config_path: 配置文件路径
        """
        self._config_path = config_path
        self._config: Optional[SystemConfig] = None
        
        if config_path:
            self.load(config_path)
        else:
            self._config = SystemConfig()
        
        logger.info("ConfigService initialized")
    
    def load(self, path: str) -> bool:
        """加载配置文件
        
        Args:
            path: 配置文件路径
            
        Returns:
            bool: 成功返回True
        """
        try:
            config_file = Path(path)
            if not config_file.exists():
                logger.warning(f"Config file not found: {path}, using defaults")
                self._config = SystemConfig()
                return False
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
            
            self._config = SystemConfig(**config_dict)
            self._config_path = path
            
            logger.info(f"Configuration loaded from: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Load configuration failed: {e}")
            self._config = SystemConfig()
            return False
    
    def save(self, path: Optional[str] = None) -> bool:
        """保存配置
        
        Args:
            path: 保存路径，None则使用当前路径
            
        Returns:
            bool: 成功返回True
        """
        try:
            if path is None:
                path = self._config_path
            
            if path is None:
                logger.error("No save path specified")
                return False
            
            config_file = Path(path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(
                    self._config.dict(),
                    f,
                    default_flow_style=False,
                    allow_unicode=True
                )
            
            logger.info(f"Configuration saved to: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Save configuration failed: {e}")
            return False
    
    def get_config(self) -> SystemConfig:
        """获取配置对象"""
        return self._config
    
    def get_hardware_config(self) -> HardwareConfig:
        """获取硬件配置"""
        return self._config.hardware
    
    def get_scan_config(self) -> ScanConfig:
        """获取扫描配置"""
        return self._config.scan
    
    def update_config(self, config_dict: Dict[str, Any]) -> bool:
        """更新配置
        
        Args:
            config_dict: 配置字典
            
        Returns:
            bool: 成功返回True
        """
        try:
            # 深度更新配置
            current_dict = self._config.dict()
            self._deep_update(current_dict, config_dict)
            
            # 重新验证
            self._config = SystemConfig(**current_dict)
            
            logger.info("Configuration updated")
            return True
            
        except Exception as e:
            logger.error(f"Update configuration failed: {e}")
            return False
    
    @staticmethod
    def _deep_update(base_dict: Dict, update_dict: Dict) -> None:
        """递归更新字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                ConfigService._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value


__all__ = ["ConfigService", "SystemConfig", "HardwareConfig", "ScanConfig"]
