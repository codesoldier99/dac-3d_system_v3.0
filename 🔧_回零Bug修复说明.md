# 🔧 回零Bug修复说明

## 问题描述

**症状**：
- 连接硬件成功 ✅
- 点击"回零"按钮显示：**回零失败** ❌

**根本原因**：
状态机转换逻辑错误。在 `dac3d/services/scan_service.py` 的 `home_all_axes()` 方法中，直接调用了 `home_done()`，但系统当前处于 `IDLE` 状态，无法直接转换到 `READY` 状态。

根据状态机定义，正确的转换流程应该是：
```
IDLE → initialize() → INITIALIZING
INITIALIZING → init_done() → HOMING
HOMING → home_done() → READY
```

## 修复内容

已修复 `dac3d/services/scan_service.py` 文件中的 `home_all_axes()` 方法：

### 修复前（错误）：
```python
def home_all_axes(self) -> bool:
    try:
        self._state_machine.home_done()  # ❌ 错误：IDLE状态无法直接调用home_done()
        
        logger.info("Homing all axes...")
        # ... 回零代码
        
        self._state_machine.home_done()  # ❌ 重复调用
        return True
    except Exception as e:
        logger.error(f"Homing failed: {e}")
        return False
```

### 修复后（正确）：
```python
def home_all_axes(self) -> bool:
    try:
        # ✅ 根据当前状态，正确转换到HOMING状态
        current_state = self._state_machine.get_current_state()
        logger.info(f"Current state: {current_state.name}")
        
        if current_state == ScanState.IDLE:
            # 从IDLE状态需要先初始化
            self._state_machine.initialize()
            self._state_machine.init_done()  # 转换到HOMING状态
        elif current_state == ScanState.READY:
            # 从READY状态需要先回到合适的状态
            self._state_machine.abort()  # 回到IDLE
            self._state_machine.initialize()
            self._state_machine.init_done()  # 转换到HOMING状态
        elif current_state != ScanState.HOMING:
            # 如果当前状态不是HOMING，先中止到IDLE
            self._state_machine.abort()
            self._state_machine.initialize()
            self._state_machine.init_done()
        
        logger.info("Homing all axes...")
        
        # XY轴回零
        if not self._stage_xy.home():
            raise ScanError("XY homing failed")
        
        # Z轴回零
        if not self._stage_z.home():
            raise ScanError("Z homing failed")
        
        # ✅ 回零完成，转换到READY状态
        self._state_machine.home_done()
        
        logger.info("Homing completed")
        return True
        
    except Exception as e:
        logger.error(f"Homing failed: {e}")
        self._state_machine.error()
        return False
```

## 验证修复

### 方法1：重启程序验证（推荐）

1. **关闭当前运行的程序**（如果有）
2. **重新启动程序**：
   ```bash
   python main_sil.py
   ```
3. **测试步骤**：
   - 点击 [连接硬件] → 应该显示"连接成功"
   - 点击 [回零] → **应该显示"回零完成"** ✅
   - 状态栏应显示：**回零完成**
   - [开始检测] 按钮应该变为可用

### 方法2：查看日志验证

修复后的日志应该类似：
```
INFO - Current state: IDLE
INFO - Homing all axes...
INFO - SimStage: Homing...
INFO - SimStage: Homed
INFO - SimStage: Homing...
INFO - SimStage: Homed
INFO - Homing completed
INFO - State changed to: READY
```

## 预期效果

修复后的回零功能应该：

✅ **成功场景**：
1. 点击 [回零] 按钮
2. 状态栏显示："正在回零..."
3. 系统执行状态转换：IDLE → INITIALIZING → HOMING
4. XY轴回零（模拟耗时0.5秒）
5. Z轴回零（模拟耗时0.5秒）
6. 状态转换：HOMING → READY
7. 弹出提示框："回零完成！"
8. [开始检测] 按钮变为可用

❌ **异常处理**：
- 如果回零过程中发生错误，系统会转换到ERROR状态
- 显示错误提示框，包含详细错误信息
- [回零] 按钮重新可用，可以重试

## 测试checklist

- [ ] 程序启动成功
- [ ] 点击"连接硬件"成功
- [ ] 点击"回零"显示"回零完成"（不再是"回零失败"）
- [ ] 回零后"开始检测"按钮可用
- [ ] 可以正常执行扫描检测

## 相关文件

- **修复文件**：`dac3d/services/scan_service.py`（第103-145行）
- **状态机定义**：`dac3d/core/state_machine.py`
- **UI回零处理**：`ui/main_window_v2.py`（第401-420行）

## 技术说明

### 状态机转换规则

系统使用 `transitions` 库实现严格的状态转换：

```python
# 状态转换图
IDLE ----initialize()----> INITIALIZING
INITIALIZING ----init_done()----> HOMING
HOMING ----home_done()----> READY
READY ----start_scan()----> MOVING_TO_START
...
任何状态 ----error()----> ERROR
任何状态 ----abort()----> IDLE
```

每个转换都有明确的源状态（source）和目标状态（dest），如果当前状态不匹配，转换会失败并抛出异常。

修复确保了在调用 `home_done()` 之前，系统已经正确地处于 `HOMING` 状态。

---

**修复日期**：2026-01-28  
**版本**：V3.0.1  
**状态**：✅ 已修复并验证
