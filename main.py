"""
DAC-3D 系统主程序入口
"""

import sys
import logging
from pathlib import Path
from PyQt5.QtWidgets import QApplication

from dac3d.services.scan_service import ScanService
from dac3d.services.config_service import ConfigService
from dac3d.hal.fpga.zynq_controller import ZynqController
from dac3d.hal.motion.zmotion_stage import ZMotionStage
from dac3d.hal.motion.pi_piezo import PIPiezoStage
from dac3d.hal.camera.basler_camera import BaslerCamera
from dac3d.hal.camera.camera_array import CameraArray
from dac3d.core.event_bus import event_bus
from ui.main_window import MainWindow


def setup_logging(log_level: str = "INFO"):
    """配置日志系统"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('dac3d.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def create_hardware(config_service: ConfigService):
    """创建硬件实例
    
    Args:
        config_service: 配置服务
        
    Returns:
        tuple: (stage_xy, stage_z, fpga, camera_array)
    """
    hw_config = config_service.get_hardware_config()
    
    # 创建FPGA控制器
    fpga = ZynqController(
        device_id="zynq_fpga",
        host=hw_config.fpga_host,
        port=hw_config.fpga_port,
        config={"encoder_resolution_nm": hw_config.encoder_resolution_nm}
    )
    
    # 创建XY运动台
    stage_xy = ZMotionStage(
        device_id="zmotion_xy",
        ip_address=hw_config.zmotion_ip,
        x_axis=hw_config.zmotion_x_axis,
        y_axis=hw_config.zmotion_y_axis,
        config={
            "speed": hw_config.zmotion_speed,
            "accel": 500.0,
            "units_per_mm": 1000.0,
            "soft_limit_x": [0, 100],
            "soft_limit_y": [0, 100]
        }
    )
    
    # 创建Z轴压电台
    stage_z = PIPiezoStage(
        device_id="pi_piezo_z",
        connection_type=hw_config.pi_connection,
        address=hw_config.pi_address,
        axis_name=hw_config.pi_axis,
        config={
            "range_min": hw_config.pi_range_min,
            "range_max": hw_config.pi_range_max
        }
    )
    
    # 创建相机阵列
    cameras = []
    for i, sn in enumerate(hw_config.camera_serial_numbers):
        cam = BaslerCamera(
            device_id=f"basler_cam_{i+1}",
            serial_number=sn,
            config={
                "exposure_us": hw_config.camera_exposure_us,
                "gain": hw_config.camera_gain,
                "trigger_mode": "hardware",
                "trigger_source": "Line1"
            }
        )
        cameras.append(cam)
    
    camera_array = CameraArray(cameras)
    
    return stage_xy, stage_z, fpga, camera_array


def main():
    """主函数"""
    # 配置日志
    setup_logging("INFO")
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("DAC-3D 产业化光学检测系统 V3.0")
    logger.info("Copyright © 2026 福特科技")
    logger.info("=" * 60)
    
    try:
        # 加载配置
        config_path = Path("configs/system.yaml")
        config_service = ConfigService(str(config_path) if config_path.exists() else None)
        logger.info(f"Configuration loaded: {config_path}")
        
        # 创建硬件
        stage_xy, stage_z, fpga, camera_array = create_hardware(config_service)
        logger.info("Hardware instances created")
        
        # 创建扫描服务
        scan_service = ScanService(
            stage_xy=stage_xy,
            stage_z=stage_z,
            fpga=fpga,
            camera_array=camera_array
        )
        logger.info("Scan service created")
        
        # 启动事件总线
        event_bus.start()
        logger.info("Event bus started")
        
        # 创建GUI应用
        app = QApplication(sys.argv)
        app.setApplicationName("DAC-3D")
        app.setOrganizationName("福特科技")
        
        # 创建主窗口
        main_window = MainWindow(
            scan_service=scan_service,
            config_service=config_service
        )
        main_window.show()
        
        logger.info("Main window displayed")
        logger.info("System ready")
        
        # 运行应用
        exit_code = app.exec_()
        
        # 清理
        event_bus.stop()
        logger.info("Event bus stopped")
        
        logger.info("Application terminated")
        return exit_code
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
