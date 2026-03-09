"""
系统集成测试 - 软件在环模式

测试完整系统功能
"""

import pytest
import logging
from pathlib import Path

from dac3d.services.scan_service import ScanService
from dac3d.services.config_service import ConfigService
from dac3d.services.database_service import DatabaseService
from dac3d.services.defect_service import DefectService
from dac3d.hal.sim.sim_fpga import SimFPGA
from dac3d.hal.sim.sim_stage import SimStage
from dac3d.hal.sim.sim_camera import SimCamera
from dac3d.hal.camera.camera_array import CameraArray
from dac3d.hal.interfaces import Position, ScanRegion


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSystemIntegration:
    """系统集成测试"""
    
    @pytest.fixture
    def simulated_hardware(self):
        """创建模拟硬件"""
        fpga = SimFPGA()
        stage_xy = SimStage("sim_xy")
        stage_z = SimStage("sim_z")
        
        cameras = [
            SimCamera(f"sim_cam_{i}", {"width": 512, "height": 512})
            for i in range(3)
        ]
        camera_array = CameraArray(cameras)
        
        return fpga, stage_xy, stage_z, camera_array
    
    @pytest.fixture
    def scan_service(self, simulated_hardware):
        """创建扫描服务"""
        fpga, stage_xy, stage_z, camera_array = simulated_hardware
        return ScanService(stage_xy, stage_z, fpga, camera_array)
    
    @pytest.fixture
    def database(self, tmp_path):
        """创建临时数据库"""
        db_path = tmp_path / "test.db"
        return DatabaseService(str(db_path))
    
    def test_hardware_connection(self, simulated_hardware):
        """测试硬件连接"""
        fpga, stage_xy, stage_z, camera_array = simulated_hardware
        
        # 测试连接
        assert fpga.connect()
        assert stage_xy.connect()
        assert stage_z.connect()
        assert camera_array.connect_all()
        
        logger.info("✓ 硬件连接测试通过")
    
    def test_homing(self, scan_service):
        """测试回零"""
        # 初始化系统
        assert scan_service.initialize_system()
        
        # 回零
        assert scan_service.home_all_axes()
        
        logger.info("✓ 回零测试通过")
    
    def test_scan_configuration(self, scan_service):
        """测试扫描配置"""
        scan_service.initialize_system()
        scan_service.home_all_axes()
        
        # 配置扫描
        region = ScanRegion(
            start=Position(0, 0, 0),
            end=Position(1, 1, 0),
            step_x=0.1,
            step_y=0.1
        )
        
        assert scan_service.configure_scan(region)
        
        logger.info("✓ 扫描配置测试通过")
    
    def test_defect_detection(self):
        """测试瑕疵检测"""
        defect_service = DefectService()
        
        # 创建模拟图像
        sim_camera = SimCamera()
        sim_camera.connect()
        sim_camera.start_acquisition()
        image = sim_camera.grab()
        
        # 检测瑕疵
        has_defect, defects = defect_service.detect_defects(image)
        
        assert image is not None
        logger.info(f"✓ 瑕疵检测测试通过: 检测到{len(defects)}个瑕疵")
    
    def test_database_operations(self, database):
        """测试数据库操作"""
        # 创建批次
        batch_id = database.create_batch("Test Batch", 144, "Tester")
        assert batch_id > 0
        
        # 保存孔位结果
        result_id = database.save_hole_result(
            batch_id=batch_id,
            hole_index=0,
            row_num=1,
            col_num=1,
            has_defect=True,
            defect_count=2,
            defect_types=["亮点", "暗点"]
        )
        assert result_id > 0
        
        # 保存瑕疵
        defect_id = database.save_defect(
            result_id=result_id,
            defect_type="亮点",
            position=(100, 200, 0),
            size_um=15.5,
            intensity=3500
        )
        assert defect_id > 0
        
        # 查询数据
        batch_info = database.get_batch_info(batch_id)
        assert batch_info is not None
        assert batch_info['batch_name'] == "Test Batch"
        
        hole_result = database.get_hole_result(batch_id, 0)
        assert hole_result is not None
        assert hole_result['has_defect'] == 1
        
        defects = database.get_defects_by_result(result_id)
        assert len(defects) == 1
        assert defects[0]['defect_type'] == "亮点"
        
        # 完成批次
        database.finish_batch(batch_id)
        
        logger.info("✓ 数据库操作测试通过")
    
    def test_full_workflow(self, scan_service, database):
        """测试完整工作流"""
        logger.info("开始完整工作流测试...")
        
        # 1. 初始化系统
        assert scan_service.initialize_system()
        logger.info("  1/5 系统初始化完成")
        
        # 2. 回零
        assert scan_service.home_all_axes()
        logger.info("  2/5 回零完成")
        
        # 3. 配置扫描
        region = ScanRegion(
            start=Position(0, 0, 0),
            end=Position(0.5, 0.5, 0),
            step_x=0.1,
            step_y=0.1
        )
        assert scan_service.configure_scan(region)
        logger.info("  3/5 扫描配置完成")
        
        # 4. 执行扫描
        assert scan_service.execute_scan()
        logger.info("  4/5 扫描执行完成")
        
        # 5. 获取数据
        scan_data = scan_service.get_scan_data()
        assert len(scan_data) > 0
        logger.info(f"  5/5 数据获取完成: {len(scan_data)} 个相机数据")
        
        logger.info("✓ 完整工作流测试通过")


def test_import_all_modules():
    """测试所有模块导入"""
    logger.info("测试模块导入...")
    
    # HAL层
    from dac3d.hal.interfaces import IDevice, IStage, ICamera, IFPGA
    from dac3d.hal.fpga.zynq_controller import ZynqController
    from dac3d.hal.motion.zmotion_stage import ZMotionStage
    from dac3d.hal.motion.pi_piezo import PIPiezoStage
    from dac3d.hal.camera.basler_camera import BaslerCamera
    from dac3d.hal.sim.sim_fpga import SimFPGA
    from dac3d.hal.sim.sim_stage import SimStage
    from dac3d.hal.sim.sim_camera import SimCamera
    
    # Core层
    from dac3d.core.state_machine import ScanStateMachine
    from dac3d.core.event_bus import EventBus
    from dac3d.core.exceptions import DAC3DError
    
    # Services层
    from dac3d.services.scan_service import ScanService
    from dac3d.services.config_service import ConfigService
    from dac3d.services.database_service import DatabaseService
    from dac3d.services.defect_service import DefectService
    
    # UI层
    from ui.well_plate_widget import WellPlateWidget
    from ui.main_window_v2 import MainWindowV2
    
    logger.info("✓ 所有模块导入成功")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
