"""
DAC-3D主窗口

基于PyQt5的主界面
"""

import logging
from typing import Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QTabWidget,
    QStatusBar, QMessageBox, QProgressBar
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont

from dac3d.services.scan_service import ScanService
from dac3d.services.config_service import ConfigService
from dac3d.hal.interfaces import Position, ScanRegion
from dac3d.core.state_machine import ScanState
from dac3d.core.event_bus import event_bus, Event, EventNames


logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    """扫描工作线程"""
    
    progress_updated = pyqtSignal(float)
    scan_completed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, scan_service: ScanService):
        super().__init__()
        self._scan_service = scan_service
    
    def run(self):
        """执行扫描"""
        try:
            success = self._scan_service.execute_scan()
            self.scan_completed.emit(success)
        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.error_occurred.emit(str(e))


class MainWindow(QMainWindow):
    """DAC-3D主窗口"""
    
    def __init__(
        self,
        scan_service: Optional[ScanService] = None,
        config_service: Optional[ConfigService] = None
    ):
        """初始化
        
        Args:
            scan_service: 扫描服务
            config_service: 配置服务
        """
        super().__init__()
        
        self._scan_service = scan_service
        self._config_service = config_service or ConfigService()
        
        self._scan_worker: Optional[ScanWorker] = None
        
        # 订阅事件
        self._subscribe_events()
        
        # 初始化UI
        self._init_ui()
        
        logger.info("MainWindow initialized")
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("DAC-3D 产业化检测系统 V3.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 左侧控制面板
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel, stretch=1)
        
        # 右侧显示区域
        display_area = self._create_display_area()
        main_layout.addWidget(display_area, stretch=3)
        
        # 状态栏
        self._create_status_bar()
        
        logger.info("UI initialized")
    
    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 标题
        title = QLabel("控制面板")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 系统控制组
        system_group = QGroupBox("系统控制")
        system_layout = QVBoxLayout()
        system_group.setLayout(system_layout)
        
        self._btn_connect = QPushButton("连接硬件")
        self._btn_connect.clicked.connect(self._on_connect_hardware)
        system_layout.addWidget(self._btn_connect)
        
        self._btn_home = QPushButton("回零")
        self._btn_home.clicked.connect(self._on_home_axes)
        self._btn_home.setEnabled(False)
        system_layout.addWidget(self._btn_home)
        
        self._btn_disconnect = QPushButton("断开连接")
        self._btn_disconnect.clicked.connect(self._on_disconnect_hardware)
        self._btn_disconnect.setEnabled(False)
        system_layout.addWidget(self._btn_disconnect)
        
        layout.addWidget(system_group)
        
        # 扫描控制组
        scan_group = QGroupBox("扫描控制")
        scan_layout = QVBoxLayout()
        scan_group.setLayout(scan_layout)
        
        self._btn_configure = QPushButton("配置扫描")
        self._btn_configure.clicked.connect(self._on_configure_scan)
        self._btn_configure.setEnabled(False)
        scan_layout.addWidget(self._btn_configure)
        
        self._btn_start_scan = QPushButton("开始扫描")
        self._btn_start_scan.clicked.connect(self._on_start_scan)
        self._btn_start_scan.setEnabled(False)
        scan_layout.addWidget(self._btn_start_scan)
        
        self._btn_stop_scan = QPushButton("停止扫描")
        self._btn_stop_scan.clicked.connect(self._on_stop_scan)
        self._btn_stop_scan.setEnabled(False)
        scan_layout.addWidget(self._btn_stop_scan)
        
        layout.addWidget(scan_group)
        
        # 状态显示
        status_group = QGroupBox("系统状态")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)
        
        self._label_state = QLabel("状态: 未初始化")
        status_layout.addWidget(self._label_state)
        
        self._label_position = QLabel("位置: --")
        status_layout.addWidget(self._label_position)
        
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        status_layout.addWidget(self._progress_bar)
        
        layout.addWidget(status_group)
        
        layout.addStretch()
        
        return panel
    
    def _create_display_area(self) -> QWidget:
        """创建显示区域"""
        tab_widget = QTabWidget()
        
        # 图像显示标签页
        image_tab = QWidget()
        image_layout = QVBoxLayout()
        image_tab.setLayout(image_layout)
        
        self._label_image = QLabel("图像显示区域")
        self._label_image.setAlignment(Qt.AlignCenter)
        self._label_image.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
        self._label_image.setMinimumHeight(400)
        image_layout.addWidget(self._label_image)
        
        tab_widget.addTab(image_tab, "图像显示")
        
        # 3D显示标签页(预留)
        viewer_3d_tab = QWidget()
        viewer_3d_layout = QVBoxLayout()
        viewer_3d_tab.setLayout(viewer_3d_layout)
        
        label_3d = QLabel("3D可视化区域\n(集成Napari)")
        label_3d.setAlignment(Qt.AlignCenter)
        label_3d.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
        label_3d.setMinimumHeight(400)
        viewer_3d_layout.addWidget(label_3d)
        
        tab_widget.addTab(viewer_3d_tab, "3D显示")
        
        # 日志标签页
        log_tab = QWidget()
        log_layout = QVBoxLayout()
        log_tab.setLayout(log_layout)
        
        self._label_log = QLabel("系统日志")
        self._label_log.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._label_log.setStyleSheet("border: 1px solid #ccc; background: white; padding: 10px;")
        self._label_log.setWordWrap(True)
        log_layout.addWidget(self._label_log)
        
        tab_widget.addTab(log_tab, "系统日志")
        
        return tab_widget
    
    def _create_status_bar(self):
        """创建状态栏"""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")
    
    def _subscribe_events(self):
        """订阅系统事件"""
        event_bus.subscribe(EventNames.STATE_CHANGED, self._on_state_changed)
        event_bus.subscribe(EventNames.SCAN_PROGRESS, self._on_scan_progress)
        event_bus.subscribe(EventNames.SCAN_COMPLETED, self._on_scan_completed)
        event_bus.subscribe(EventNames.HARDWARE_CONNECTED, self._on_hardware_connected)
    
    # ============== 事件处理 ==============
    
    def _on_connect_hardware(self):
        """连接硬件"""
        if not self._scan_service:
            QMessageBox.warning(self, "错误", "扫描服务未初始化")
            return
        
        self._status_bar.showMessage("正在连接硬件...")
        self._btn_connect.setEnabled(False)
        
        try:
            success = self._scan_service.initialize_system()
            if success:
                self._status_bar.showMessage("硬件连接成功")
                self._btn_home.setEnabled(True)
                self._btn_disconnect.setEnabled(True)
            else:
                QMessageBox.critical(self, "错误", "硬件连接失败")
                self._btn_connect.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"连接失败: {e}")
            self._btn_connect.setEnabled(True)
    
    def _on_disconnect_hardware(self):
        """断开硬件"""
        # 实现断开逻辑
        self._btn_connect.setEnabled(True)
        self._btn_home.setEnabled(False)
        self._btn_disconnect.setEnabled(False)
        self._btn_configure.setEnabled(False)
        self._btn_start_scan.setEnabled(False)
        self._status_bar.showMessage("已断开连接")
    
    def _on_home_axes(self):
        """回零"""
        if not self._scan_service:
            return
        
        self._status_bar.showMessage("正在回零...")
        self._btn_home.setEnabled(False)
        
        try:
            success = self._scan_service.home_all_axes()
            if success:
                self._status_bar.showMessage("回零完成")
                self._btn_configure.setEnabled(True)
            else:
                QMessageBox.critical(self, "错误", "回零失败")
            self._btn_home.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"回零失败: {e}")
            self._btn_home.setEnabled(True)
    
    def _on_configure_scan(self):
        """配置扫描"""
        if not self._scan_service:
            return
        
        # 简单配置(实际应该弹出配置对话框)
        region = ScanRegion(
            start=Position(0, 0, 0),
            end=Position(10, 10, 0),
            step_x=0.1,
            step_y=0.1
        )
        
        try:
            success = self._scan_service.configure_scan(region)
            if success:
                self._status_bar.showMessage("扫描配置完成")
                self._btn_start_scan.setEnabled(True)
                QMessageBox.information(self, "提示", f"扫描配置完成\n总点数: {region.total_points}")
            else:
                QMessageBox.critical(self, "错误", "扫描配置失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"配置失败: {e}")
    
    def _on_start_scan(self):
        """开始扫描"""
        if not self._scan_service:
            return
        
        self._status_bar.showMessage("扫描中...")
        self._btn_start_scan.setEnabled(False)
        self._btn_stop_scan.setEnabled(True)
        self._progress_bar.setValue(0)
        
        # 启动扫描线程
        self._scan_worker = ScanWorker(self._scan_service)
        self._scan_worker.progress_updated.connect(self._update_progress)
        self._scan_worker.scan_completed.connect(self._on_scan_finished)
        self._scan_worker.error_occurred.connect(self._on_scan_error)
        self._scan_worker.start()
    
    def _on_stop_scan(self):
        """停止扫描"""
        if self._scan_service:
            self._scan_service.stop_scan()
        self._btn_stop_scan.setEnabled(False)
        self._btn_start_scan.setEnabled(True)
        self._status_bar.showMessage("扫描已停止")
    
    def _on_state_changed(self, event: Event):
        """状态变化"""
        state: ScanState = event.data["state"]
        self._label_state.setText(f"状态: {state.name}")
    
    def _on_scan_progress(self, event: Event):
        """扫描进度"""
        progress = event.data.get("progress", 0)
        self._progress_bar.setValue(int(progress * 100))
    
    def _on_scan_completed(self, event: Event):
        """扫描完成"""
        n_frames = event.data.get("n_frames", 0)
        self._status_bar.showMessage(f"扫描完成, 采集 {n_frames} 帧")
    
    def _on_hardware_connected(self, event: Event):
        """硬件连接"""
        logger.info("Hardware connected event received")
    
    def _update_progress(self, progress: float):
        """更新进度"""
        self._progress_bar.setValue(int(progress * 100))
    
    def _on_scan_finished(self, success: bool):
        """扫描完成"""
        self._btn_stop_scan.setEnabled(False)
        self._btn_start_scan.setEnabled(True)
        self._progress_bar.setValue(100 if success else 0)
        
        if success:
            QMessageBox.information(self, "完成", "扫描完成!")
            self._status_bar.showMessage("扫描完成")
        else:
            QMessageBox.warning(self, "提示", "扫描未完全成功")
    
    def _on_scan_error(self, error_msg: str):
        """扫描错误"""
        QMessageBox.critical(self, "错误", f"扫描错误: {error_msg}")
        self._btn_stop_scan.setEnabled(False)
        self._btn_start_scan.setEnabled(True)
    
    def closeEvent(self, event):
        """关闭窗口"""
        reply = QMessageBox.question(
            self,
            '确认',
            '确定要退出吗?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 清理资源
            if self._scan_worker and self._scan_worker.isRunning():
                self._scan_worker.terminate()
                self._scan_worker.wait()
            event.accept()
        else:
            event.ignore()


__all__ = ["MainWindow"]
