"""
FPGA控制器单元测试示例
"""

import pytest
from dac3d.hal.fpga.registers import RegisterMap, RegisterValidator, PSOMode
from dac3d.hal.interfaces import TriggerConfig


class TestRegisterMap:
    """寄存器映射测试"""
    
    def test_make_ctrl_word(self):
        """测试控制字生成"""
        ctrl = RegisterMap.make_ctrl_word(
            global_en=True,
            pso_en=True
        )
        assert ctrl & 0x01 == 0x01  # global_en
        assert ctrl & 0x04 == 0x04  # pso_en
    
    def test_parse_status(self):
        """测试状态寄存器解析"""
        status = 0x00010001  # busy=1, frame_count=1
        result = RegisterMap.parse_status(status)
        
        assert result["busy"] == True
        assert result["frame_count"] == 1
    
    def test_position_conversion(self):
        """测试位置单位转换"""
        # 100μm @ 1nm分辨率 = 100000计数
        count = RegisterMap.encode_position_um_to_count(100.0, 1.0)
        assert count == 100000
        
        # 反向转换
        pos = RegisterMap.decode_count_to_position_um(100000, 1.0)
        assert pos == 100.0
    
    def test_time_conversion(self):
        """测试时间单位转换"""
        # 1000ns = 100 FPGA单位(10ns)
        units = RegisterMap.ns_to_fpga_units(1000)
        assert units == 100
        
        # 反向转换
        ns = RegisterMap.fpga_units_to_ns(100)
        assert ns == 1000


class TestRegisterValidator:
    """寄存器验证器测试"""
    
    def test_pwm_period_validation(self):
        """测试PWM周期验证"""
        assert RegisterValidator.validate_pwm_period(1000) == True
        assert RegisterValidator.validate_pwm_period(50) == False  # 太小
        assert RegisterValidator.validate_pwm_period(20000) == False  # 太大
    
    def test_pwm_duty_validation(self):
        """测试占空比验证"""
        assert RegisterValidator.validate_pwm_duty(0.5) == True
        assert RegisterValidator.validate_pwm_duty(0.0) == True
        assert RegisterValidator.validate_pwm_duty(1.0) == True
        assert RegisterValidator.validate_pwm_duty(-0.1) == False
        assert RegisterValidator.validate_pwm_duty(1.1) == False
    
    def test_interval_validation(self):
        """测试触发间隔验证"""
        assert RegisterValidator.validate_interval(10000) == True  # 10μm
        assert RegisterValidator.validate_interval(500) == False  # 太小
        assert RegisterValidator.validate_interval(20000000) == False  # 太大


class TestTriggerConfig:
    """触发配置测试"""
    
    def test_trigger_config_creation(self):
        """测试触发配置创建"""
        config = TriggerConfig(
            mode='position',
            start_pos=0.0,
            end_pos=1000.0,
            interval=10.0,
            pulse_width_ns=1000
        )
        
        assert config.mode == 'position'
        assert config.start_pos == 0.0
        assert config.end_pos == 1000.0
        assert config.interval == 10.0
    
    def test_trigger_config_validation(self):
        """测试触发配置验证"""
        # 有效配置
        config1 = TriggerConfig(mode='position', interval=10.0)
        assert config1.validate() == True
        
        # 无效模式
        config2 = TriggerConfig(mode='invalid', interval=10.0)
        assert config2.validate() == False
        
        # 无效间隔
        config3 = TriggerConfig(mode='position', interval=-1.0)
        assert config3.validate() == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
