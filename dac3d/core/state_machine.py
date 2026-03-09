"""
扫描状态机

严格控制系统状态转换，确保流程可控
"""

import logging
from enum import Enum, auto
from typing import Dict, Callable, Optional, Any
from transitions import Machine

from dac3d.core.exceptions import StateTransitionError
from dac3d.core.event_bus import event_bus, Event, EventNames


logger = logging.getLogger(__name__)


class ScanState(Enum):
    """扫描状态枚举"""
    IDLE = auto()              # 空闲
    INITIALIZING = auto()      # 初始化中
    HOMING = auto()            # 回零中
    READY = auto()             # 就绪
    CONFIGURING = auto()       # 配置中
    MOVING_TO_START = auto()   # 移动到起点
    SCANNING = auto()          # 扫描中
    PROCESSING = auto()        # 处理中
    SAVING = auto()            # 保存中
    COMPLETE = auto()          # 完成
    PAUSED = auto()            # 暂停
    ERROR = auto()             # 错误


class ScanStateMachine:
    """扫描流程状态机
    
    使用transitions库实现严格的状态转换控制
    """
    
    # 定义所有状态
    states = [state.name for state in ScanState]
    
    # 定义状态转换规则
    transitions = [
        # 从IDLE开始
        {'trigger': 'initialize', 'source': 'IDLE', 'dest': 'INITIALIZING'},
        {'trigger': 'init_done', 'source': 'INITIALIZING', 'dest': 'HOMING'},
        
        # 回零流程
        {'trigger': 'home_done', 'source': 'HOMING', 'dest': 'READY'},
        
        # 配置扫描参数
        {'trigger': 'configure', 'source': 'READY', 'dest': 'CONFIGURING'},
        {'trigger': 'config_done', 'source': 'CONFIGURING', 'dest': 'READY'},
        
        # 开始扫描
        {'trigger': 'start_scan', 'source': 'READY', 'dest': 'MOVING_TO_START'},
        {'trigger': 'at_start', 'source': 'MOVING_TO_START', 'dest': 'SCANNING'},
        
        # 扫描完成
        {'trigger': 'scan_done', 'source': 'SCANNING', 'dest': 'PROCESSING'},
        {'trigger': 'process_done', 'source': 'PROCESSING', 'dest': 'SAVING'},
        {'trigger': 'save_done', 'source': 'SAVING', 'dest': 'COMPLETE'},
        
        # 完成后返回就绪
        {'trigger': 'reset_to_ready', 'source': 'COMPLETE', 'dest': 'READY'},
        
        # 暂停/恢复
        {'trigger': 'pause', 'source': 'SCANNING', 'dest': 'PAUSED'},
        {'trigger': 'resume', 'source': 'PAUSED', 'dest': 'SCANNING'},
        
        # 任何状态都可以进入错误
        {'trigger': 'error', 'source': '*', 'dest': 'ERROR'},
        
        # 从错误恢复到空闲
        {'trigger': 'recover', 'source': 'ERROR', 'dest': 'IDLE'},
        
        # 紧急停止到空闲
        {'trigger': 'abort', 'source': '*', 'dest': 'IDLE'},
    ]
    
    def __init__(self):
        """初始化状态机"""
        self.machine = Machine(
            model=self,
            states=ScanStateMachine.states,
            transitions=ScanStateMachine.transitions,
            initial='IDLE',
            auto_transitions=False,  # 禁用自动转换，必须显式调用trigger
            send_event=True,  # 向回调传递事件对象
        )
        
        # 状态进入回调
        self._enter_callbacks: Dict[str, Callable] = {}
        
        # 状态退出回调
        self._exit_callbacks: Dict[str, Callable] = {}
        
        # 注册所有状态的进入/退出回调
        for state_name in ScanStateMachine.states:
            self.machine.add_transition(
                trigger=f'_on_enter_{state_name}',
                source='*',
                dest=state_name,
                before=f'_notify_enter_{state_name}'
            )
        
        logger.info("ScanStateMachine initialized")
    
    def register_enter_callback(self, state: ScanState, callback: Callable) -> None:
        """注册状态进入回调
        
        Args:
            state: 状态
            callback: 回调函数
        """
        self._enter_callbacks[state.name] = callback
        logger.debug(f"Registered enter callback for state: {state.name}")
    
    def register_exit_callback(self, state: ScanState, callback: Callable) -> None:
        """注册状态退出回调"""
        self._exit_callbacks[state.name] = callback
        logger.debug(f"Registered exit callback for state: {state.name}")
    
    def get_current_state(self) -> ScanState:
        """获取当前状态"""
        return ScanState[self.state]
    
    def can_transition_to(self, target_state: ScanState) -> bool:
        """检查是否可以转换到目标状态
        
        Args:
            target_state: 目标状态
            
        Returns:
            bool: 可以转换返回True
        """
        # 获取当前状态的所有可能转换
        current_state = self.state
        for transition in ScanStateMachine.transitions:
            if (transition['source'] == current_state or transition['source'] == '*') and \
               transition['dest'] == target_state.name:
                return True
        return False
    
    def _notify_state_change(self, event_data: Any) -> None:
        """通知状态变化"""
        try:
            current_state = self.get_current_state()
            
            # 执行进入回调
            if current_state.name in self._enter_callbacks:
                self._enter_callbacks[current_state.name]()
            
            # 发布事件（修复event_data可能为None的问题）
            timestamp = None
            if event_data and hasattr(event_data, 'transition'):
                timestamp = event_data.transition.timestamp if hasattr(event_data.transition, 'timestamp') else None
            
            event_bus.publish(Event(
                name=EventNames.STATE_CHANGED,
                data={"state": current_state, "timestamp": timestamp},
                source="state_machine"
            ))
            
            logger.info(f"State changed to: {current_state.name}")
            
        except Exception as e:
            logger.error(f"State change notification error: {e}")
    
    def __getattribute__(self, name: str) -> Any:
        """拦截状态转换，添加日志"""
        attr = object.__getattribute__(self, name)
        
        # 如果是trigger方法，包装它
        if name in ['initialize', 'init_done', 'home_done', 'configure', 'config_done',
                    'start_scan', 'at_start', 'scan_done', 'process_done', 'save_done',
                    'reset_to_ready', 'pause', 'resume', 'error', 'recover', 'abort']:
            def wrapped(*args, **kwargs):
                try:
                    result = attr(*args, **kwargs)
                    self._notify_state_change(None)
                    return result
                except Exception as e:
                    logger.error(f"State transition '{name}' failed: {e}")
                    raise StateTransitionError(f"Cannot transition: {e}")
            return wrapped
        
        return attr


__all__ = ["ScanState", "ScanStateMachine"]
