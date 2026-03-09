"""
数据库服务

使用SQLite管理检测数据
"""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json


logger = logging.getLogger(__name__)


class DatabaseService:
    """数据库服务
    
    管理检测结果、瑕疵记录、统计数据等
    """
    
    def __init__(self, db_path: str = "data/dac3d.db"):
        """初始化
        
        Args:
            db_path: 数据库文件路径
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._conn: Optional[sqlite3.Connection] = None
        
        # 连接数据库并初始化表结构
        self._connect()
        self._init_tables()
        
        logger.info(f"DatabaseService initialized: {db_path}")
    
    def _connect(self):
        """连接数据库"""
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row  # 支持字典访问
        logger.info("Database connected")
    
    def _init_tables(self):
        """初始化数据库表结构"""
        cursor = self._conn.cursor()
        
        # 检测批次表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                total_holes INTEGER DEFAULT 144,
                scanned_holes INTEGER DEFAULT 0,
                defect_holes INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                operator TEXT,
                notes TEXT
            )
        """)
        
        # 孔位检测结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hole_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                hole_index INTEGER NOT NULL,
                row_num INTEGER NOT NULL,
                col_num INTEGER NOT NULL,
                scan_time TEXT NOT NULL,
                has_defect INTEGER DEFAULT 0,
                defect_count INTEGER DEFAULT 0,
                defect_types TEXT,
                confidence REAL,
                image_path TEXT,
                notes TEXT,
                FOREIGN KEY (batch_id) REFERENCES batches (batch_id)
            )
        """)
        
        # 瑕疵详细表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS defects (
                defect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                defect_type TEXT NOT NULL,
                position_x REAL,
                position_y REAL,
                position_z REAL,
                size_um REAL,
                intensity REAL,
                description TEXT,
                FOREIGN KEY (result_id) REFERENCES hole_results (result_id)
            )
        """)
        
        # 系统配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                config_key TEXT PRIMARY KEY,
                config_value TEXT,
                update_time TEXT
            )
        """)
        
        # 统计数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_date TEXT NOT NULL,
                total_batches INTEGER DEFAULT 0,
                total_holes INTEGER DEFAULT 0,
                defect_holes INTEGER DEFAULT 0,
                defect_rate REAL DEFAULT 0.0
            )
        """)
        
        self._conn.commit()
        logger.info("Database tables initialized")
    
    def create_batch(
        self,
        batch_name: str,
        total_holes: int = 144,
        operator: str = ""
    ) -> int:
        """创建新的检测批次
        
        Args:
            batch_name: 批次名称
            total_holes: 总孔位数
            operator: 操作员
            
        Returns:
            int: 批次ID
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO batches (batch_name, start_time, total_holes, operator, status)
            VALUES (?, ?, ?, ?, 'running')
        """, (batch_name, datetime.now().isoformat(), total_holes, operator))
        
        self._conn.commit()
        batch_id = cursor.lastrowid
        
        logger.info(f"Created batch: {batch_name} (ID={batch_id})")
        return batch_id
    
    def save_hole_result(
        self,
        batch_id: int,
        hole_index: int,
        row_num: int,
        col_num: int,
        has_defect: bool,
        defect_count: int = 0,
        defect_types: List[str] = None,
        confidence: float = 1.0,
        image_path: str = "",
        notes: str = ""
    ) -> int:
        """保存孔位检测结果
        
        Returns:
            int: 结果ID
        """
        cursor = self._conn.cursor()
        
        defect_types_json = json.dumps(defect_types) if defect_types else "[]"
        
        cursor.execute("""
            INSERT INTO hole_results (
                batch_id, hole_index, row_num, col_num, scan_time,
                has_defect, defect_count, defect_types, confidence,
                image_path, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_id, hole_index, row_num, col_num, datetime.now().isoformat(),
            1 if has_defect else 0, defect_count, defect_types_json, confidence,
            image_path, notes
        ))
        
        self._conn.commit()
        result_id = cursor.lastrowid
        
        # 更新批次统计
        self._update_batch_stats(batch_id)
        
        logger.debug(f"Saved hole result: batch={batch_id}, hole={hole_index}, defect={has_defect}")
        return result_id
    
    def save_defect(
        self,
        result_id: int,
        defect_type: str,
        position: tuple = (0, 0, 0),
        size_um: float = 0,
        intensity: float = 0,
        description: str = ""
    ) -> int:
        """保存瑕疵详情
        
        Returns:
            int: 瑕疵ID
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO defects (
                result_id, defect_type, position_x, position_y, position_z,
                size_um, intensity, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result_id, defect_type, position[0], position[1], position[2],
            size_um, intensity, description
        ))
        
        self._conn.commit()
        defect_id = cursor.lastrowid
        
        logger.debug(f"Saved defect: result={result_id}, type={defect_type}")
        return defect_id
    
    def _update_batch_stats(self, batch_id: int):
        """更新批次统计"""
        cursor = self._conn.cursor()
        
        # 统计已扫描孔位数和瑕疵孔位数
        cursor.execute("""
            SELECT COUNT(*) as scanned, SUM(has_defect) as defects
            FROM hole_results
            WHERE batch_id = ?
        """, (batch_id,))
        
        row = cursor.fetchone()
        scanned = row['scanned'] or 0
        defects = row['defects'] or 0
        
        cursor.execute("""
            UPDATE batches
            SET scanned_holes = ?, defect_holes = ?
            WHERE batch_id = ?
        """, (scanned, defects, batch_id))
        
        self._conn.commit()
    
    def finish_batch(self, batch_id: int, notes: str = ""):
        """完成批次"""
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE batches
            SET end_time = ?, status = 'completed', notes = ?
            WHERE batch_id = ?
        """, (datetime.now().isoformat(), notes, batch_id))
        
        self._conn.commit()
        logger.info(f"Batch {batch_id} finished")
    
    def get_batch_info(self, batch_id: int) -> Optional[Dict]:
        """获取批次信息"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_hole_result(self, batch_id: int, hole_index: int) -> Optional[Dict]:
        """获取孔位结果"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM hole_results
            WHERE batch_id = ? AND hole_index = ?
        """, (batch_id, hole_index))
        
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result['defect_types'] = json.loads(result.get('defect_types', '[]'))
            return result
        return None
    
    def get_defects_by_result(self, result_id: int) -> List[Dict]:
        """获取某个孔位的所有瑕疵"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM defects WHERE result_id = ?
        """, (result_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_batch_results(self, batch_id: int) -> List[Dict]:
        """获取批次所有结果"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM hole_results
            WHERE batch_id = ?
            ORDER BY hole_index
        """, (batch_id,))
        
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            result['defect_types'] = json.loads(result.get('defect_types', '[]'))
            results.append(result)
        
        return results
    
    def get_recent_batches(self, limit: int = 10) -> List[Dict]:
        """获取最近的批次"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM batches
            ORDER BY batch_id DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self, date: str = None) -> Dict:
        """获取统计数据
        
        Args:
            date: 日期(YYYY-MM-DD)，None表示今天
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        cursor = self._conn.cursor()
        
        # 统计今日数据
        cursor.execute("""
            SELECT 
                COUNT(*) as total_batches,
                SUM(total_holes) as total_holes,
                SUM(defect_holes) as defect_holes
            FROM batches
            WHERE DATE(start_time) = ?
        """, (date,))
        
        row = cursor.fetchone()
        
        total_batches = row['total_batches'] or 0
        total_holes = row['total_holes'] or 0
        defect_holes = row['defect_holes'] or 0
        defect_rate = (defect_holes / total_holes * 100) if total_holes > 0 else 0.0
        
        return {
            "date": date,
            "total_batches": total_batches,
            "total_holes": total_holes,
            "defect_holes": defect_holes,
            "defect_rate": defect_rate
        }
    
    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            logger.info("Database connection closed")


__all__ = ["DatabaseService"]
