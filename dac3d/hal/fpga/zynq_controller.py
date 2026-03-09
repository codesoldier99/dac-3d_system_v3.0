"""
Zynq FPGA控制器实现

支持通过以太网与Zynq ARM端通信，控制FPGA逻辑
"""

import socket
import struct
import time
from typing import Dict, Any, Optional
import logging

from dac3d.hal.interfaces import (
    IFPGA,
    DeviceState,
    TriggerConfig,
    Position,
)
from dac3d.hal.fpga.registers import (
    RegisterAddress,
    RegisterMap,
    RegisterValidator,
    PSOMode,
    FPGAState,
)


logger = logging.getLogger(__name__)


class ZynqProtocol:
    """Zynq通信协议
    
    使用TCP Socket与ARM端通信
    协议格式:
        请求: [CMD(1B)] [ADDR(4B)] [DATA(4B)] [CHECKSUM(1B)]
        响应: [STATUS(1B)] [DATA(4B)] [CHECKSUM(1B)]
    """
    
    # 命令码
    CMD_READ = 0x01
    CMD_WRITE = 0x02
    CMD_BURST_READ = 0x03
    CMD_BURST_WRITE = 0x04
    CMD_RESET = 0xFF
    
    # 状态码
    STATUS_OK = 0x00
    STATUS_ERROR = 0x01
    STATUS_TIMEOUT = 0x02
    STATUS_INVALID = 0x03
    
    @staticmethod
    def make_request(cmd: int, addr: int, data: int = 0) -> bytes:
        """构造请求包
        
        Args:
            cmd: 命令码
            addr: 地址
            data: 数据(写命令时使用)
            
        Returns:
            bytes: 请求包
        """
        # 打包为: CMD(1B) ADDR(4B) DATA(4B)
        packet = struct.pack(">BII", cmd, addr, data)
        # 计算简单校验和
        checksum = sum(packet) & 0xFF
        return packet + bytes([checksum])
    
    @staticmethod
    def parse_response(resp: bytes) -> tuple[int, int]:
        """解析响应包
        
        Args:
            resp: 响应包
            
        Returns:
            tuple: (status, data)
        """
        if len(resp) < 6:
            raise ValueError("Response too short")
        
        status, data, checksum = struct.unpack(">BIB", resp)
        
        # 验证校验和
        calc_checksum = sum(resp[:-1]) & 0xFF
        if calc_checksum != checksum:
            raise ValueError("Checksum mismatch")
        
        return status, data


class ZynqController(IFPGA):
    """Zynq FPGA控制器
    
    通过TCP连接到Zynq ARM端，进行寄存器读写和配置
    """
    
    def __init__(
        self,
        device_id: str = "zynq_fpga",
        host: str = "192.168.1.10",
        port: int = 5000,
        config: Optional[Dict[str, Any]] = None
    ):
        """初始化
        
        Args:
            device_id: 设备ID
            host: Zynq IP地址
            port: TCP端口
            config: 配置字典
        """
        super().__init__(device_id, config)
        self._host = host
        self._port = port
        self._socket: Optional[socket.socket] = None
        self._timeout = 5.0  # 秒
        
        # 编码器分辨率(nm)
        self._encoder_res_nm = config.get("encoder_resolution_nm", 1.0) if config else 1.0
        
        # 内部状态缓存
        self._last_frame_count = 0
        self._fpga_version = 0
        
        logger.info(f"ZynqController initialized: {host}:{port}")
    
    def connect(self) -> bool:
        """连接到Zynq"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self._timeout)
            self._socket.connect((self._host, self._port))
            
            # 读取版本号
            self._fpga_version = self.read_register(RegisterAddress.VERSION)
            logger.info(f"Connected to Zynq FPGA, version: 0x{self._fpga_version:08X}")
            
            # 软复位
            self.reset()
            
            self._state = DeviceState.CONNECTED
            return True
            
        except Exception as e:
            self._error_msg = f"Connection failed: {e}"
            logger.error(self._error_msg)
            self._state = DeviceState.ERROR
            return False
    
    def disconnect(self) -> bool:
        """断开连接"""
        try:
            if self._socket:
                self._socket.close()
                self._socket = None
            self._state = DeviceState.DISCONNECTED
            logger.info("Disconnected from Zynq")
            return True
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return False
    
    def reset(self) -> bool:
        """软复位FPGA逻辑"""
        try:
            # 设置复位位
            ctrl = RegisterMap.make_ctrl_word(soft_reset=True)
            self.write_register(RegisterAddress.CTRL, ctrl)
            time.sleep(0.01)
            
            # 清除复位位，使能全局
            ctrl = RegisterMap.make_ctrl_word(global_en=True)
            self.write_register(RegisterAddress.CTRL, ctrl)
            time.sleep(0.01)
            
            logger.info("FPGA reset completed")
            self._state = DeviceState.IDLE
            return True
            
        except Exception as e:
            self._error_msg = f"Reset failed: {e}"
            logger.error(self._error_msg)
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取设备信息"""
        return {
            "device_id": self._device_id,
            "type": "Zynq-7020 FPGA",
            "host": self._host,
            "port": self._port,
            "version": f"0x{self._fpga_version:08X}",
            "state": self._state.name,
            "encoder_resolution_nm": self._encoder_res_nm,
        }
    
    def write_register(self, addr: int, value: int) -> bool:
        """写寄存器
        
        Args:
            addr: 寄存器地址
            value: 写入值(32位)
            
        Returns:
            bool: 成功返回True
        """
        if not self._socket:
            logger.error("Not connected")
            return False
        
        try:
            # 构造请求
            request = ZynqProtocol.make_request(ZynqProtocol.CMD_WRITE, addr, value)
            self._socket.sendall(request)
            
            # 接收响应
            response = self._socket.recv(6)
            status, _ = ZynqProtocol.parse_response(response)
            
            if status != ZynqProtocol.STATUS_OK:
                logger.error(f"Write register failed: addr=0x{addr:02X}, status={status}")
                return False
            
            logger.debug(f"Write register: addr=0x{addr:02X}, value=0x{value:08X}")
            return True
            
        except Exception as e:
            self._error_msg = f"Write register error: {e}"
            logger.error(self._error_msg)
            return False
    
    def read_register(self, addr: int) -> int:
        """读寄存器
        
        Args:
            addr: 寄存器地址
            
        Returns:
            int: 寄存器值
        """
        if not self._socket:
            logger.error("Not connected")
            return 0
        
        try:
            # 构造请求
            request = ZynqProtocol.make_request(ZynqProtocol.CMD_READ, addr)
            self._socket.sendall(request)
            
            # 接收响应
            response = self._socket.recv(6)
            status, data = ZynqProtocol.parse_response(response)
            
            if status != ZynqProtocol.STATUS_OK:
                logger.error(f"Read register failed: addr=0x{addr:02X}, status={status}")
                return 0
            
            logger.debug(f"Read register: addr=0x{addr:02X}, value=0x{data:08X}")
            return data
            
        except Exception as e:
            self._error_msg = f"Read register error: {e}"
            logger.error(self._error_msg)
            return 0
    
    def configure_pso(self, config: TriggerConfig) -> bool:
        """配置位置同步输出(PSO)
        
        Args:
            config: 触发配置
            
        Returns:
            bool: 成功返回True
        """
        if not config.validate():
            logger.error("Invalid trigger config")
            return False
        
        try:
            # 停止当前PSO
            self.stop_pso()
            
            # 转换位置单位
            start_count = RegisterMap.encode_position_um_to_count(
                config.start_pos, self._encoder_res_nm
            )
            end_count = RegisterMap.encode_position_um_to_count(
                config.end_pos, self._encoder_res_nm
            )
            interval_count = RegisterMap.encode_position_um_to_count(
                config.interval, self._encoder_res_nm
            )
            
            # 验证参数
            if not RegisterValidator.validate_position(start_count):
                logger.error(f"Invalid start position: {start_count}")
                return False
            if not RegisterValidator.validate_position(end_count):
                logger.error(f"Invalid end position: {end_count}")
                return False
            if not RegisterValidator.validate_interval(interval_count):
                logger.error(f"Invalid interval: {interval_count}")
                return False
            
            # 写入寄存器
            self.write_register(RegisterAddress.PSO_START, start_count & 0xFFFFFFFF)
            self.write_register(RegisterAddress.PSO_END, end_count & 0xFFFFFFFF)
            self.write_register(RegisterAddress.PSO_INTERVAL, interval_count & 0xFFFFFFFF)
            
            # 配置模式(默认单次扫描)
            self.write_register(RegisterAddress.PSO_MODE, PSOMode.SINGLE)
            
            # 配置触发脉冲宽度和延迟
            width_units = RegisterMap.ns_to_fpga_units(config.pulse_width_ns)
            delay_units = RegisterMap.ns_to_fpga_units(config.delay_ns)
            self.write_register(RegisterAddress.TRIG_WIDTH, width_units)
            self.write_register(RegisterAddress.TRIG_DELAY, delay_units)
            
            logger.info(
                f"PSO configured: start={config.start_pos}μm, end={config.end_pos}μm, "
                f"interval={config.interval}μm, width={config.pulse_width_ns}ns"
            )
            
            self._state = DeviceState.READY
            return True
            
        except Exception as e:
            self._error_msg = f"Configure PSO failed: {e}"
            logger.error(self._error_msg)
            self._state = DeviceState.ERROR
            return False
    
    def start_pso(self) -> bool:
        """启动PSO触发"""
        try:
            # 设置PSO使能位
            ctrl = RegisterMap.make_ctrl_word(global_en=True, pso_en=True, arm=True)
            self.write_register(RegisterAddress.CTRL, ctrl)
            
            logger.info("PSO started")
            self._state = DeviceState.BUSY
            return True
            
        except Exception as e:
            self._error_msg = f"Start PSO failed: {e}"
            logger.error(self._error_msg)
            return False
    
    def stop_pso(self) -> bool:
        """停止PSO触发"""
        try:
            # 清除PSO使能位
            ctrl = RegisterMap.make_ctrl_word(global_en=True)
            self.write_register(RegisterAddress.CTRL, ctrl)
            
            logger.info("PSO stopped")
            self._state = DeviceState.IDLE
            return True
            
        except Exception as e:
            logger.error(f"Stop PSO failed: {e}")
            return False
    
    def get_encoder_position(self, axis: str) -> float:
        """获取编码器位置
        
        Args:
            axis: 'x', 'y', 'z'
            
        Returns:
            float: 位置(微米)
        """
        axis = axis.lower()
        
        if axis == 'x':
            count = self.read_register(RegisterAddress.ENC_X_POS)
        elif axis == 'y':
            count = self.read_register(RegisterAddress.ENC_Y_POS)
        elif axis == 'z':
            count = self.read_register(RegisterAddress.ENC_Z_POS)
        else:
            logger.error(f"Invalid axis: {axis}")
            return 0.0
        
        # 转换为有符号整数
        if count & 0x80000000:
            count = count - 0x100000000
        
        # 转换为微米
        pos_um = RegisterMap.decode_count_to_position_um(count, self._encoder_res_nm)
        return pos_um
    
    def get_frame_count(self) -> int:
        """获取触发帧计数"""
        status = self.read_register(RegisterAddress.STATUS)
        from dac3d.hal.fpga.registers import RegisterMap
        status_dict = RegisterMap.parse_status(status)
        self._last_frame_count = status_dict["frame_count"]
        return self._last_frame_count
    
    def get_timestamp(self) -> int:
        """获取时间戳
        
        Returns:
            int: 时间戳(微秒)
        """
        return self.read_register(RegisterAddress.TIMESTAMP)
    
    def set_pwm(self, channel: int, period_ns: int, duty: float) -> bool:
        """设置PWM输出
        
        Args:
            channel: 通道号(0-3)
            period_ns: 周期(纳秒)
            duty: 占空比(0.0-1.0)
            
        Returns:
            bool: 成功返回True
        """
        if channel < 0 or channel > 3:
            logger.error(f"Invalid PWM channel: {channel}")
            return False
        
        if not RegisterValidator.validate_pwm_duty(duty):
            logger.error(f"Invalid duty cycle: {duty}")
            return False
        
        try:
            # 转换周期
            period_units = RegisterMap.ns_to_fpga_units(period_ns)
            if not RegisterValidator.validate_pwm_period(period_units):
                logger.error(f"Invalid PWM period: {period_ns}ns")
                return False
            
            # 写入周期(所有通道共享)
            self.write_register(RegisterAddress.PWM_PERIOD, period_units)
            
            # 写入占空比
            duty_units = int(period_units * duty)
            duty_addr = RegisterAddress.PWM_DUTY_0 + (channel * 4)
            self.write_register(duty_addr, duty_units)
            
            logger.debug(
                f"PWM configured: ch={channel}, period={period_ns}ns, duty={duty:.2%}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Set PWM failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取FPGA状态
        
        Returns:
            Dict: 状态信息
        """
        status_reg = self.read_register(RegisterAddress.STATUS)
        status_dict = RegisterMap.parse_status(status_reg)
        
        # 读取位置
        pos_x = self.get_encoder_position('x')
        pos_y = self.get_encoder_position('y')
        pos_z = self.get_encoder_position('z')
        
        return {
            "busy": status_dict["busy"],
            "error": status_dict["error"],
            "pso_active": status_dict["pso_active"],
            "state": status_dict["state"].name,
            "frame_count": status_dict["frame_count"],
            "position": {"x": pos_x, "y": pos_y, "z": pos_z},
            "timestamp_us": self.get_timestamp(),
        }
    
    def wait_idle(self, timeout_s: float = 60.0) -> bool:
        """等待FPGA进入空闲状态
        
        Args:
            timeout_s: 超时时间(秒)
            
        Returns:
            bool: 成功返回True，超时返回False
        """
        start_time = time.time()
        
        while True:
            status = self.get_status()
            if not status["busy"]:
                logger.info("FPGA is idle")
                return True
            
            if time.time() - start_time > timeout_s:
                logger.error("Wait idle timeout")
                return False
            
            time.sleep(0.1)


__all__ = ["ZynqController", "ZynqProtocol"]
