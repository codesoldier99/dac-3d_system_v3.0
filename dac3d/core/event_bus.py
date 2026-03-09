"""
事件总线

用于系统内模块间解耦通信
"""

import logging
from typing import Callable, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
import threading


logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件数据结构"""
    name: str
    data: Any = None
    timestamp: datetime = None
    source: str = ""
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventBus:
    """事件总线(单例模式)
    
    实现发布-订阅模式，支持异步事件分发
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._subscribers: Dict[str, List[Callable]] = {}
            self._event_queue: Queue = Queue()
            self._running = False
            self._worker_thread = None
            self._initialized = True
            
            logger.info("EventBus initialized")
    
    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> None:
        """订阅事件
        
        Args:
            event_name: 事件名称
            callback: 回调函数
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        
        if callback not in self._subscribers[event_name]:
            self._subscribers[event_name].append(callback)
            logger.debug(f"Subscribed to event: {event_name}")
    
    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """取消订阅"""
        if event_name in self._subscribers:
            if callback in self._subscribers[event_name]:
                self._subscribers[event_name].remove(callback)
                logger.debug(f"Unsubscribed from event: {event_name}")
    
    def publish(self, event: Event) -> None:
        """发布事件(同步)
        
        Args:
            event: 事件对象
        """
        if event.name in self._subscribers:
            for callback in self._subscribers[event.name]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")
        
        logger.debug(f"Event published: {event.name}")
    
    def publish_async(self, event: Event) -> None:
        """发布事件(异步)"""
        self._event_queue.put(event)
    
    def start(self) -> None:
        """启动事件处理线程"""
        if not self._running:
            self._running = True
            self._worker_thread = threading.Thread(target=self._process_events, daemon=True)
            self._worker_thread.start()
            logger.info("EventBus started")
    
    def stop(self) -> None:
        """停止事件处理"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)
        logger.info("EventBus stopped")
    
    def _process_events(self) -> None:
        """事件处理工作线程"""
        while self._running:
            try:
                event = self._event_queue.get(timeout=0.1)
                self.publish(event)
            except:
                continue
    
    def clear_all(self) -> None:
        """清除所有订阅"""
        self._subscribers.clear()
        logger.info("All subscriptions cleared")


# 全局事件总线实例
event_bus = EventBus()


# 预定义事件名称
class EventNames:
    """标准事件名称"""
    # 硬件事件
    HARDWARE_CONNECTED = "hardware.connected"
    HARDWARE_DISCONNECTED = "hardware.disconnected"
    HARDWARE_ERROR = "hardware.error"
    
    # 扫描事件
    SCAN_STARTED = "scan.started"
    SCAN_PROGRESS = "scan.progress"
    SCAN_COMPLETED = "scan.completed"
    SCAN_ABORTED = "scan.aborted"
    
    # 状态变化
    STATE_CHANGED = "state.changed"
    
    # 图像事件
    IMAGE_ACQUIRED = "image.acquired"
    IMAGE_PROCESSED = "image.processed"
    
    # 数据事件
    DATA_SAVED = "data.saved"
    DATA_LOADED = "data.loaded"


__all__ = ["Event", "EventBus", "event_bus", "EventNames"]
