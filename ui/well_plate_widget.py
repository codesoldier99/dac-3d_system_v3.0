"""
144孔物料盘显示控件

优雅的可视化界面，显示12x12孔位阵列
"""

import logging
from typing import Optional, Dict
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPainterPath


logger = logging.getLogger(__name__)


class WellPlateWidget(QWidget):
    """144孔物料盘显示控件
    
    显示12行x12列=144个孔位
    支持状态显示：未检测(灰色)、检测中(蓝色)、合格(绿色)、不合格(红色)
    """
    
    # 信号：孔位被点击
    hole_clicked = pyqtSignal(int)  # 发送孔位索引
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 孔板参数
        self.rows = 12
        self.cols = 12
        self.total_holes = self.rows * self.cols
        
        # 孔位状态: 0=未检测, 1=检测中, 2=合格, 3=不合格
        self._hole_states = [0] * self.total_holes
        
        # 当前扫描位置（用于显示箭头）
        self._current_hole = -1
        
        # 选中的孔位
        self._selected_hole = -1
        
        # 界面参数
        self._hole_size = 40  # 孔位直径
        self._hole_spacing = 10  # 孔位间距
        self._margin = 30  # 边距
        
        # 颜色方案
        self._colors = {
            0: QColor(220, 220, 220),  # 未检测 - 浅灰
            1: QColor(100, 150, 255),  # 检测中 - 蓝色
            2: QColor(76, 175, 80),    # 合格 - 绿色
            3: QColor(244, 67, 54),    # 不合格 - 红色
        }
        
        # 设置最小尺寸
        width = self._margin * 2 + self.cols * (self._hole_size + self._hole_spacing)
        height = self._margin * 2 + self.rows * (self._hole_size + self._hole_spacing) + 50
        self.setMinimumSize(width, height)
        
        # 启用鼠标跟踪
        self.setMouseTracking(True)
        
        logger.info("WellPlateWidget initialized: 12x12 = 144 holes")
    
    @staticmethod
    def hole_index_to_name(hole_index: int) -> str:
        """将孔位索引转换为孔位名称
        
        Args:
            hole_index: 孔位索引 (0-143)
            
        Returns:
            str: 孔位名称，如 "A1", "B5", "L12"
        """
        if not (0 <= hole_index < 144):
            return f"Unknown({hole_index})"
        
        row = hole_index // 12  # 0-11
        col = hole_index % 12   # 0-11
        
        row_name = chr(ord('A') + row)  # A-L
        col_name = str(col + 1)  # 1-12
        
        return f"{row_name}{col_name}"
    
    def set_hole_state(self, hole_index: int, state: int):
        """设置孔位状态
        
        Args:
            hole_index: 孔位索引 (0-143)
            state: 状态 (0=未检测, 1=检测中, 2=合格, 3=不合格)
        """
        if 0 <= hole_index < self.total_holes:
            self._hole_states[hole_index] = state
            self.update()
    
    def set_current_hole(self, hole_index: int):
        """设置当前扫描孔位（显示箭头）
        
        Args:
            hole_index: 孔位索引
        """
        self._current_hole = hole_index
        self.update()
    
    def set_selected_hole(self, hole_index: int):
        """设置选中的孔位
        
        Args:
            hole_index: 孔位索引
        """
        self._selected_hole = hole_index
        self.update()
    
    def reset_all(self):
        """重置所有孔位状态"""
        self._hole_states = [0] * self.total_holes
        self._current_hole = -1
        self._selected_hole = -1
        self.update()
    
    def get_hole_position(self, hole_index: int) -> QPoint:
        """获取孔位中心位置
        
        Args:
            hole_index: 孔位索引
            
        Returns:
            QPoint: 中心坐标
        """
        row = hole_index // self.cols
        col = hole_index % self.cols
        
        x = self._margin + col * (self._hole_size + self._hole_spacing) + self._hole_size // 2
        y = self._margin + row * (self._hole_size + self._hole_spacing) + self._hole_size // 2
        
        return QPoint(x, y)
    
    def get_hole_at_position(self, pos: QPoint) -> int:
        """根据鼠标位置获取孔位索引
        
        Args:
            pos: 鼠标位置
            
        Returns:
            int: 孔位索引，-1表示无效
        """
        for i in range(self.total_holes):
            center = self.get_hole_position(i)
            distance = ((pos.x() - center.x())**2 + (pos.y() - center.y())**2)**0.5
            
            if distance <= self._hole_size // 2:
                return i
        
        return -1
    
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制标题
        self._draw_title(painter)
        
        # 绘制行列标签
        self._draw_labels(painter)
        
        # 绘制所有孔位
        for i in range(self.total_holes):
            self._draw_hole(painter, i)
        
        # 绘制当前扫描位置箭头
        if 0 <= self._current_hole < self.total_holes:
            self._draw_arrow(painter, self._current_hole)
        
        # 绘制统计信息
        self._draw_statistics(painter)
    
    def _draw_title(self, painter: QPainter):
        """绘制标题"""
        painter.setPen(QColor(60, 60, 60))
        font = QFont("Arial", 14, QFont.Bold)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 5, self.width(), 20),
            Qt.AlignCenter,
            "144孔物料盘检测视图"
        )
    
    def _draw_labels(self, painter: QPainter):
        """绘制行列标签"""
        painter.setPen(QColor(100, 100, 100))
        font = QFont("Arial", 9)
        painter.setFont(font)
        
        # 列标签 (A-L)
        for col in range(self.cols):
            label = chr(65 + col)  # A, B, C...
            x = self._margin + col * (self._hole_size + self._hole_spacing) + self._hole_size // 2
            y = self._margin - 10
            painter.drawText(QRect(x-10, y, 20, 15), Qt.AlignCenter, label)
        
        # 行标签 (1-12)
        for row in range(self.rows):
            label = str(row + 1)
            x = self._margin - 20
            y = self._margin + row * (self._hole_size + self._hole_spacing) + self._hole_size // 2
            painter.drawText(QRect(x, y-7, 15, 15), Qt.AlignCenter, label)
    
    def _draw_hole(self, painter: QPainter, hole_index: int):
        """绘制单个孔位
        
        Args:
            painter: 绘图器
            hole_index: 孔位索引
        """
        center = self.get_hole_position(hole_index)
        state = self._hole_states[hole_index]
        
        # 获取颜色
        color = self._colors.get(state, QColor(200, 200, 200))
        
        # 如果是选中的孔位，加深边框
        if hole_index == self._selected_hole:
            painter.setPen(QPen(QColor(0, 0, 0), 3))
        else:
            painter.setPen(QPen(QColor(150, 150, 150), 1))
        
        painter.setBrush(QBrush(color))
        
        # 绘制圆形孔位
        painter.drawEllipse(
            center.x() - self._hole_size // 2,
            center.y() - self._hole_size // 2,
            self._hole_size,
            self._hole_size
        )
        
        # 绘制孔位编号（可选）
        if self._hole_size > 30:
            painter.setPen(QColor(80, 80, 80))
            font = QFont("Arial", 7)
            painter.setFont(font)
            # 使用静态方法获取孔位名称
            text = self.hole_index_to_name(hole_index)
            painter.drawText(
                QRect(center.x()-15, center.y()-7, 30, 15),
                Qt.AlignCenter,
                text
            )
    
    def _draw_arrow(self, painter: QPainter, hole_index: int):
        """绘制指向当前孔位的箭头
        
        Args:
            painter: 绘图器
            hole_index: 孔位索引
        """
        center = self.get_hole_position(hole_index)
        
        # 箭头位置（孔位右侧）
        arrow_x = center.x() + self._hole_size // 2 + 15
        arrow_y = center.y()
        
        # 设置画笔
        painter.setPen(QPen(QColor(255, 152, 0), 2))  # 橙色
        painter.setBrush(QBrush(QColor(255, 152, 0)))
        
        # 绘制箭头
        path = QPainterPath()
        path.moveTo(arrow_x, arrow_y)
        path.lineTo(arrow_x - 10, arrow_y - 6)
        path.lineTo(arrow_x - 10, arrow_y + 6)
        path.closeSubpath()
        
        painter.drawPath(path)
    
    def _draw_statistics(self, painter: QPainter):
        """绘制统计信息"""
        # 统计各状态数量
        total = self.total_holes
        scanned = sum(1 for s in self._hole_states if s in [2, 3])
        passed = sum(1 for s in self._hole_states if s == 2)
        failed = sum(1 for s in self._hole_states if s == 3)
        
        # 绘制统计文本
        y_offset = self._margin + self.rows * (self._hole_size + self._hole_spacing) + 20
        
        painter.setPen(QColor(60, 60, 60))
        font = QFont("Arial", 10)
        painter.setFont(font)
        
        stats_text = (
            f"已检测: {scanned}/{total}   "
            f"合格: {passed}   "
            f"不合格: {failed}   "
            f"良率: {(passed/scanned*100 if scanned > 0 else 0):.1f}%"
        )
        
        painter.drawText(
            QRect(self._margin, y_offset, self.width() - 2*self._margin, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            stats_text
        )
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            hole_index = self.get_hole_at_position(event.pos())
            if hole_index >= 0:
                self._selected_hole = hole_index
                self.hole_clicked.emit(hole_index)
                self.update()
                logger.debug(f"Hole {hole_index} clicked")


__all__ = ["WellPlateWidget"]
