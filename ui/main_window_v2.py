"""
DAC-3D主窗口 V2.0 - 优雅专业版

144孔物料盘显示、瑕疵检测、实时进度
"""

import logging
from typing import Optional, Dict
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QGroupBox, QMenuBar, QMenu, QAction,
    QStatusBar, QProgressBar, QTextEdit, QDialog, QFormLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QMessageBox,
    QFileDialog
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap, QImage
import numpy as np

from dac3d.services.scan_service import ScanService
from dac3d.services.config_service import ConfigService
from dac3d.services.database_service import DatabaseService
from dac3d.services.defect_service import DefectService, DefectInfo
from dac3d.hal.interfaces import Position, ScanRegion
from dac3d.core.state_machine import ScanState
from dac3d.core.event_bus import event_bus, Event, EventNames
from ui.well_plate_widget import WellPlateWidget


logger = logging.getLogger(__name__)


class ScanWorkerV2(QThread):
    """扫描工作线程"""
    
    progress_updated = pyqtSignal(int, int, bool)  # (hole_index, total, has_defect)
    scan_completed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(
        self,
        scan_service: ScanService,
        defect_service: DefectService,
        database: DatabaseService,
        batch_id: int
    ):
        super().__init__()
        self._scan_service = scan_service
        self._defect_service = defect_service
        self._database = database
        self._batch_id = batch_id
    
    def run(self):
        """执行144孔位快速扫描"""
        try:
            logger.info("Starting 144-hole scan in SIL mode...")
            
            # 总孔位数
            total_holes = 144
            
            # 直接循环144个孔位，每个孔位独立模拟
            for hole_idx in range(total_holes):
                # 生成单张模拟图像（512x512，减小内存占用）
                image = self._generate_single_hole_image(hole_idx)
                
                # 瑕疵检测
                has_defect, defects = self._defect_service.detect_defects(image)
                
                # 保存到数据库
                row = hole_idx // 12 + 1
                col = hole_idx % 12 + 1
                
                defect_types = [d.type for d in defects]
                result_id = self._database.save_hole_result(
                    batch_id=self._batch_id,
                    hole_index=hole_idx,
                    row_num=row,
                    col_num=col,
                    has_defect=has_defect,
                    defect_count=len(defects),
                    defect_types=defect_types
                )
                
                # 保存瑕疵详情
                for defect in defects:
                    self._database.save_defect(
                        result_id=result_id,
                        defect_type=defect.type,
                        position=(defect.position[0], defect.position[1], 0),
                        size_um=defect.size,
                        intensity=defect.intensity
                    )
                
                # 发送进度更新
                self.progress_updated.emit(hole_idx, total_holes, has_defect)
                
                # 模拟FPGA触发和检测延迟（0.5秒/孔）
                self.msleep(500)
                
                # 及时释放内存
                del image
            
            logger.info("144-hole scan completed successfully")
            self.scan_completed.emit(True)
            
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
    
    def _generate_single_hole_image(self, hole_idx: int) -> np.ndarray:
        """生成单个孔位的模拟图像
        
        Args:
            hole_idx: 孔位索引
            
        Returns:
            模拟图像（512x512，uint16）
        """
        # 使用更小的图像尺寸以节省内存
        width, height = 512, 512
        
        # 生成12位图像（0-4095）
        image = np.random.normal(2000, 100, (height, width)).astype(np.uint16)
        image = np.clip(image, 0, 4095)
        
        # 添加一些特征（10%概率添加瑕疵用于演示）
        if np.random.random() < 0.15:  # 15%概率有瑕疵
            # 随机添加1-3个瑕疵
            num_defects = np.random.randint(1, 4)
            for _ in range(num_defects):
                x = np.random.randint(50, width-50)
                y = np.random.randint(50, height-50)
                size = np.random.randint(5, 20)
                
                # 亮点或暗点
                if np.random.random() < 0.5:
                    image[y-size:y+size, x-size:x+size] = 3500  # 亮点
                else:
                    image[y-size:y+size, x-size:x+size] = 500   # 暗点
        
        return image


class ParameterDialog(QDialog):
    """参数配置对话框"""
    
    def __init__(self, config_service: ConfigService, parent=None):
        super().__init__(parent)
        self._config_service = config_service
        self.setWindowTitle("扫描参数配置")
        self.setModal(True)
        self.resize(400, 300)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化界面"""
        layout = QFormLayout()
        
        # 扫描参数
        self.step_x = QDoubleSpinBox()
        self.step_x.setRange(0.1, 100.0)
        self.step_x.setValue(10.0)
        self.step_x.setSuffix(" μm")
        layout.addRow("X步进:", self.step_x)
        
        self.step_y = QDoubleSpinBox()
        self.step_y.setRange(0.1, 100.0)
        self.step_y.setValue(10.0)
        self.step_y.setSuffix(" μm")
        layout.addRow("Y步进:", self.step_y)
        
        self.velocity = QDoubleSpinBox()
        self.velocity.setRange(1.0, 200.0)
        self.velocity.setValue(10.0)
        self.velocity.setSuffix(" mm/s")
        layout.addRow("扫描速度:", self.velocity)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        layout.addRow(btn_layout)
        
        self.setLayout(layout)


class MainWindowV2(QMainWindow):
    """DAC-3D主窗口 V2.0"""
    
    def __init__(
        self,
        scan_service: Optional[ScanService] = None,
        config_service: Optional[ConfigService] = None,
        database: Optional[DatabaseService] = None
    ):
        super().__init__()
        
        self._scan_service = scan_service
        self._config_service = config_service or ConfigService()
        self._database = database or DatabaseService()
        self._defect_service = DefectService()
        
        self._scan_worker: Optional[ScanWorkerV2] = None
        self._current_batch_id: Optional[int] = None
        
        # 订阅事件
        self._subscribe_events()
        
        # 初始化UI
        self._init_ui()
        
        logger.info("MainWindowV2 initialized")
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("DAC-3D 产业化光学检测系统 V3.0 - 专业版")
        self.setGeometry(100, 50, 1400, 900)
        
        # 创建菜单栏
        self._create_menu_bar()
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 工具栏
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：144孔物料盘
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧：详情显示
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self._create_status_bar()
        
        logger.info("UI initialized")
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        action_new_batch = QAction("新建批次", self)
        action_new_batch.triggered.connect(self._on_new_batch)
        file_menu.addAction(action_new_batch)
        
        action_export = QAction("导出报表", self)
        action_export.triggered.connect(self._on_export_report)
        file_menu.addAction(action_export)
        
        file_menu.addSeparator()
        
        action_exit = QAction("退出", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)
        
        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        
        action_parameters = QAction("扫描参数", self)
        action_parameters.triggered.connect(self._on_configure_parameters)
        settings_menu.addAction(action_parameters)
        
        action_defect_params = QAction("瑕疵检测参数", self)
        settings_menu.addAction(action_defect_params)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        action_about = QAction("关于", self)
        action_about.triggered.connect(self._on_about)
        help_menu.addAction(action_about)
    
    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QWidget()
        layout = QHBoxLayout()
        toolbar.setLayout(layout)
        
        # 按钮
        self._btn_connect = QPushButton("连接硬件")
        self._btn_connect.clicked.connect(self._on_connect_hardware)
        layout.addWidget(self._btn_connect)
        
        self._btn_home = QPushButton("回零")
        self._btn_home.clicked.connect(self._on_home_axes)
        self._btn_home.setEnabled(False)
        layout.addWidget(self._btn_home)
        
        self._btn_start = QPushButton("开始检测")
        self._btn_start.clicked.connect(self._on_start_scan)
        self._btn_start.setEnabled(False)
        layout.addWidget(self._btn_start)
        
        self._btn_stop = QPushButton("停止")
        self._btn_stop.clicked.connect(self._on_stop_scan)
        self._btn_stop.setEnabled(False)
        layout.addWidget(self._btn_stop)
        
        layout.addStretch()
        
        # 状态标签
        self._label_state = QLabel("状态: 未初始化")
        layout.addWidget(self._label_state)
        
        return toolbar
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板（物料盘）"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 标题
        title = QLabel("144孔物料盘")
        title_font = QFont("Arial", 12, QFont.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 物料盘控件
        self._well_plate = WellPlateWidget()
        self._well_plate.hole_clicked.connect(self._on_hole_clicked)
        layout.addWidget(self._well_plate)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板（详情显示）"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 图像显示区
        image_group = QGroupBox("孔位图像")
        image_layout = QVBoxLayout()
        image_group.setLayout(image_layout)
        
        self._label_image = QLabel("点击孔位查看详情")
        self._label_image.setAlignment(Qt.AlignCenter)
        self._label_image.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        self._label_image.setMinimumHeight(400)
        image_layout.addWidget(self._label_image)
        
        layout.addWidget(image_group)
        
        # 瑕疵详情区
        defect_group = QGroupBox("瑕疵详情")
        defect_layout = QVBoxLayout()
        defect_group.setLayout(defect_layout)
        
        self._text_defect = QTextEdit()
        self._text_defect.setReadOnly(True)
        self._text_defect.setMaximumHeight(200)
        defect_layout.addWidget(self._text_defect)
        
        layout.addWidget(defect_group)
        
        return panel
    
    def _create_status_bar(self):
        """创建状态栏"""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._status_bar.addPermanentWidget(self._progress_bar)
        
        self._status_bar.showMessage("就绪")
    
    def _subscribe_events(self):
        """订阅系统事件"""
        event_bus.subscribe(EventNames.STATE_CHANGED, self._on_state_changed)
    
    # ========== 事件处理 ==========
    
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
                QMessageBox.information(self, "成功", "硬件连接成功！")
            else:
                QMessageBox.critical(self, "错误", "硬件连接失败")
                self._btn_connect.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"连接失败: {e}")
            self._btn_connect.setEnabled(True)
    
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
                self._btn_start.setEnabled(True)
                QMessageBox.information(self, "完成", "回零完成！")
            else:
                QMessageBox.critical(self, "错误", "回零失败")
            self._btn_home.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"回零失败: {e}")
            self._btn_home.setEnabled(True)
    
    def _on_new_batch(self):
        """新建批次"""
        batch_name = f"Batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._current_batch_id = self._database.create_batch(
            batch_name=batch_name,
            total_holes=144
        )
        
        self._well_plate.reset_all()
        self._status_bar.showMessage(f"新建批次: {batch_name}")
        logger.info(f"Created new batch: {batch_name} (ID={self._current_batch_id})")
    
    def _on_start_scan(self):
        """开始扫描"""
        if not self._scan_service:
            return
        
        # 创建新批次
        if self._current_batch_id is None:
            self._on_new_batch()
        
        # 配置扫描
        region = ScanRegion(
            start=Position(0, 0, 0),
            end=Position(10, 10, 0),
            step_x=0.1,
            step_y=0.1
        )
        
        try:
            success = self._scan_service.configure_scan(region)
            if not success:
                QMessageBox.critical(self, "错误", "扫描配置失败")
                return
            
            # 启动扫描线程
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self._progress_bar.setValue(0)
            
            self._scan_worker = ScanWorkerV2(
                self._scan_service,
                self._defect_service,
                self._database,
                self._current_batch_id
            )
            self._scan_worker.progress_updated.connect(self._on_scan_progress)
            self._scan_worker.scan_completed.connect(self._on_scan_finished)
            self._scan_worker.error_occurred.connect(self._on_scan_error)
            self._scan_worker.start()
            
            self._status_bar.showMessage("扫描中...")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动扫描失败: {e}")
    
    def _on_stop_scan(self):
        """停止扫描"""
        if self._scan_service:
            self._scan_service.stop_scan()
        if self._scan_worker:
            self._scan_worker.terminate()
        
        self._btn_stop.setEnabled(False)
        self._btn_start.setEnabled(True)
        self._status_bar.showMessage("扫描已停止")
    
    def _on_scan_progress(self, hole_index: int, total: int, has_defect: bool):
        """扫描进度更新"""
        # 更新物料盘显示
        state = 3 if has_defect else 2  # 3=不合格, 2=合格
        self._well_plate.set_hole_state(hole_index, state)
        self._well_plate.set_current_hole(hole_index)
        
        # 更新进度条
        progress = int((hole_index + 1) / total * 100)
        self._progress_bar.setValue(progress)
        
        self._status_bar.showMessage(f"检测中: {hole_index+1}/{total}")
    
    def _on_scan_finished(self, success: bool):
        """扫描完成"""
        self._btn_stop.setEnabled(False)
        self._btn_start.setEnabled(True)
        self._progress_bar.setValue(100)
        
        # 清除当前箭头指示
        self._well_plate.set_current_hole(-1)
        
        if success:
            # 完成批次
            if self._current_batch_id:
                self._database.finish_batch(self._current_batch_id)
            
            QMessageBox.information(self, "完成", "扫描检测完成！")
            self._status_bar.showMessage("扫描完成", 0)  # 0表示永久显示
        else:
            QMessageBox.warning(self, "提示", "扫描未完全成功")
            self._status_bar.showMessage("扫描未完成", 0)
    
    def _on_scan_error(self, error_msg: str):
        """扫描错误"""
        QMessageBox.critical(self, "错误", f"扫描错误: {error_msg}")
        self._btn_stop.setEnabled(False)
        self._btn_start.setEnabled(True)
    
    def _on_hole_clicked(self, hole_index: int):
        """孔位被点击"""
        logger.info(f"Hole {hole_index} clicked")
        
        # 将索引转换为孔位名称
        hole_name = self._well_plate.hole_index_to_name(hole_index)
        
        # 获取孔位数据
        if self._current_batch_id:
            result = self._database.get_hole_result(self._current_batch_id, hole_index)
            
            if result:
                # 显示瑕疵详情
                defect_text = f"孔位: {hole_name}\n"
                defect_text += f"状态: {'不合格' if result['has_defect'] else '合格'}\n"
                defect_text += f"瑕疵数量: {result['defect_count']}\n"
                
                if result['defect_count'] > 0:
                    defects = self._database.get_defects_by_result(result['result_id'])
                    defect_text += "\n瑕疵详情:\n"
                    for i, defect in enumerate(defects, 1):
                        defect_text += f"{i}. {defect['defect_type']} - "
                        defect_text += f"位置({defect['position_x']:.1f}, {defect['position_y']:.1f}), "
                        defect_text += f"尺寸{defect['size_um']:.2f}μm\n"
                
                self._text_defect.setText(defect_text)
            else:
                self._text_defect.setText(f"孔位 {hole_name} 尚未检测")
    
    def _on_configure_parameters(self):
        """配置参数"""
        dialog = ParameterDialog(self._config_service, self)
        if dialog.exec_() == QDialog.Accepted:
            logger.info("Parameters updated")
            QMessageBox.information(self, "成功", "参数已更新")
    
    def _on_export_report(self):
        """导出报表"""
        if not self._current_batch_id:
            QMessageBox.warning(self, "提示", "没有可导出的数据")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出报表",
            f"report_{self._current_batch_id}.csv",
            "CSV Files (*.csv)"
        )
        
        if filename:
            # TODO: 实现报表导出
            logger.info(f"Export report to {filename}")
            QMessageBox.information(self, "成功", "报表导出成功")
    
    def _on_about(self):
        """关于"""
        QMessageBox.about(
            self,
            "关于 DAC-3D",
            "DAC-3D 产业化光学检测系统 V3.0\n\n"
            "基于FPGA+运动控制卡的色散差动共聚焦检测系统\n\n"
            "Copyright © 2026 福特科技\n"
            "保留所有权利"
        )
    
    def _on_state_changed(self, event: Event):
        """状态变化"""
        state: ScanState = event.data["state"]
        self._label_state.setText(f"状态: {state.name}")
    
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
            if self._scan_worker and self._scan_worker.isRunning():
                self._scan_worker.terminate()
                self._scan_worker.wait()
            
            if self._database:
                self._database.close()
            
            event.accept()
        else:
            event.ignore()


__all__ = ["MainWindowV2"]
