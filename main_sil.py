"""
DAC-3D 系统主程序 - 软件在环(SIL)模式

支持脱离真实硬件运行，用于开发和测试
"""

import sys
import logging
from pathlib import Path
from PyQt5.QtWidgets import QApplication

from dac3d.services.scan_service import ScanService
from dac3d.services.config_service import ConfigService
from dac3d.services.database_service import DatabaseService
from dac3d.hal.sim.sim_fpga import SimFPGA
from dac3d.hal.sim.sim_stage import SimStage
from dac3d.hal.sim.sim_camera import SimCamera
from dac3d.hal.camera.camera_array import CameraArray
from dac3d.core.event_bus import event_bus
from ui.main_window_v2 import MainWindowV2


def setup_logging(log_level: str = "INFO"):
    """配置日志系统"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('dac3d_sil.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def create_simulated_hardware(config_service: ConfigService):
    """创建模拟硬件实例（软件在环）
    
    Args:
        config_service: 配置服务
        
    Returns:
        tuple: (stage_xy, stage_z, fpga, camera_array)
    """
    hw_config = config_service.get_hardware_config()
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("创建模拟硬件（软件在环模式）")
    logger.info("=" * 60)
    
    # 创建模拟FPGA控制器
    fpga = SimFPGA(
        device_id="sim_fpga",
        config={"encoder_resolution_nm": hw_config.encoder_resolution_nm}
    )
    logger.info("✓ 模拟FPGA控制器创建完成")
    
    # 创建模拟XY运动台
    stage_xy = SimStage(
        device_id="sim_stage_xy",
        config={
            "velocity": hw_config.zmotion_speed,
            "acceleration": 500.0
        }
    )
    logger.info("✓ 模拟XY运动台创建完成")
    
    # 创建模拟Z轴压电台
    stage_z = SimStage(
        device_id="sim_stage_z",
        config={
            "velocity": 10.0,
            "acceleration": 100.0
        }
    )
    logger.info("✓ 模拟Z轴压电台创建完成")
    
    # 创建模拟相机阵列（优化：使用512x512图像以节省内存）
    cameras = []
    for i in range(3):
        cam = SimCamera(
            device_id=f"sim_camera_{i+1}",
            config={
                "width": 512,   # 优化：从2048减小到512
                "height": 512,  # 优化：从2048减小到512
                "exposure_us": hw_config.camera_exposure_us,
                "gain": hw_config.camera_gain
            }
        )
        cameras.append(cam)
        logger.info(f"✓ 模拟相机{i+1}创建完成")
    
    camera_array = CameraArray(cameras)
    logger.info("✓ 相机阵列创建完成")
    
    logger.info("=" * 60)
    logger.info("所有模拟硬件创建完成！")
    logger.info("系统运行在软件在环(SIL)模式")
    logger.info("=" * 60)
    
    return stage_xy, stage_z, fpga, camera_array


def main():
    """主函数"""
    # 配置日志
    setup_logging("INFO")
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 70)
    logger.info("  DAC-3D 产业化光学检测系统 V3.0 - 软件在环(SIL)模式")
    logger.info("  Software-in-Loop Simulation Mode")
    logger.info("=" * 70)
    logger.info("  Copyright © 2026 福特科技")
    logger.info("=" * 70)
    
    try:
        # 加载配置
        config_path = Path("configs/system.yaml")
        config_service = ConfigService(str(config_path) if config_path.exists() else None)
        logger.info(f"✓ 配置加载完成: {config_path}")
        
        # 创建数据库
        database = DatabaseService("data/dac3d_sil.db")
        logger.info("✓ 数据库初始化完成")
        
        # 创建模拟硬件（软件在环）
        stage_xy, stage_z, fpga, camera_array = create_simulated_hardware(config_service)
        
        # 创建扫描服务
        scan_service = ScanService(
            stage_xy=stage_xy,
            stage_z=stage_z,
            fpga=fpga,
            camera_array=camera_array
        )
        logger.info("✓ 扫描服务创建完成")
        
        # 启动事件总线
        event_bus.start()
        logger.info("✓ 事件总线启动完成")
        
        # 创建GUI应用
        app = QApplication(sys.argv)
        app.setApplicationName("DAC-3D (SIL)")
        app.setOrganizationName("福特科技")
        
        # 设置样式
        app.setStyle("Fusion")
        
        # 创建主窗口
        main_window = MainWindowV2(
            scan_service=scan_service,
            config_service=config_service,
            database=database
        )
        main_window.show()
        
        logger.info("=" * 70)
        logger.info("  主界面显示完成")
        logger.info("  系统就绪 - 软件在环模式运行中")
        logger.info("=" * 70)
        
        # 运行应用
        exit_code = app.exec_()
        
        # 清理
        event_bus.stop()
        logger.info("事件总线已停止")
        
        logger.info("=" * 70)
        logger.info("  应用程序正常退出")
        logger.info("=" * 70)
        return exit_code
        
    except Exception as e:
        logger.critical(f"致命错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
