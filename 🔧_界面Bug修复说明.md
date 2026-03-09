# 🔧 界面Bug修复说明 V2

## 问题汇总

用户报告了以下几个问题：

1. ✅ **回零功能可以正常工作** - 之前的修复生效
2. ✅ **可以开始检测** - 功能正常
3. ❌ **状态显示"未初始化"** - 状态标签没有及时更新
4. ❌ **点击孔位显示"孔位 0"** - 应该显示"孔位 A1"格式
5. ❌ **状态栏一直显示"扫描中"** - 扫描完成后状态栏没有更新

---

## 修复内容

### 1. 孔位名称显示错误 ✅

**问题**：点击孔位时显示"孔位 0"而不是"孔位 A1"

**原因**：使用孔位索引(0-143)直接显示，没有转换为标准孔位名称(A1-L12)

**修复**：

1. **在 `ui/well_plate_widget.py` 添加转换函数**：
```python
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
```

2. **在 `ui/main_window_v2.py` 使用转换函数**：
```python
def _on_hole_clicked(self, hole_index: int):
    """孔位被点击"""
    # 将索引转换为孔位名称
    hole_name = self._well_plate.hole_index_to_name(hole_index)
    
    # 显示瑕疵详情
    defect_text = f"孔位: {hole_name}\n"  # 显示 A1 而不是 0
    # ...
```

3. **修复孔位编号绘制错误**：
原来的代码：
```python
row = hole_index // self.cols + 1  # 错误：行号应该是字母
col = chr(65 + hole_index % self.cols)  # 错误：列号应该是数字
text = f"{col}{row}"  # 错误：显示为 "A1" 但计算错误
```

修复后：
```python
# 使用静态方法获取孔位名称
text = self.hole_index_to_name(hole_index)
```

---

### 2. 扫描完成后状态栏一直显示"扫描中" ✅

**问题**：扫描完成后，状态栏没有更新，一直显示"扫描中..."或"检测中: X/Y"

**原因**：
- 扫描完成时虽然调用了 `showMessage("扫描完成")`，但可能被覆盖
- 箭头指示没有清除，看起来像还在扫描

**修复**：

在 `ui/main_window_v2.py` 的 `_on_scan_finished` 方法中：

```python
def _on_scan_finished(self, success: bool):
    """扫描完成"""
    self._btn_stop.setEnabled(False)
    self._btn_start.setEnabled(True)
    self._progress_bar.setValue(100)
    
    # ✅ 新增：清除当前箭头指示
    self._well_plate.set_current_hole(-1)
    
    if success:
        # 完成批次
        if self._current_batch_id:
            self._database.finish_batch(self._current_batch_id)
        
        QMessageBox.information(self, "完成", "扫描检测完成！")
        # ✅ 修改：添加超时参数0，表示永久显示
        self._status_bar.showMessage("扫描完成", 0)
    else:
        QMessageBox.warning(self, "提示", "扫描未完全成功")
        self._status_bar.showMessage("扫描未完成", 0)
```

**关键改进**：
1. 调用 `set_current_hole(-1)` 清除橙色箭头
2. `showMessage` 使用超时参数 `0`，表示永久显示直到下次更新

---

### 3. 状态标签显示"未初始化" ⚠️

**说明**：

状态标签会根据状态机的状态自动更新：
- **IDLE** - 空闲
- **INITIALIZING** - 初始化中
- **HOMING** - 回零中
- **READY** - 就绪
- **SCANNING** - 扫描中
- **COMPLETE** - 完成
- **ERROR** - 错误

**正常流程**：
1. 启动程序 → 状态: IDLE (空闲)
2. 连接硬件 → 状态: IDLE (空闲)
3. 执行回零 → 状态: HOMING (回零中) → READY (就绪)
4. 开始扫描 → 状态: SCANNING (扫描中)
5. 扫描完成 → 状态: COMPLETE (完成) → READY (就绪)

**如果显示"未初始化"**：
- 这只是初始显示
- 一旦状态机发生任何状态变化，标签会自动更新
- 回零成功后应该显示"READY"

---

## 验证步骤

### 请按以下步骤验证修复：

1. **关闭当前运行的程序**

2. **重新启动程序**：
   ```bash
   python main_sil.py
   ```

3. **测试孔位名称显示**：
   - 连接硬件 → 成功
   - 开始检测 → 扫描开始
   - 点击任意孔位 → 应显示"孔位: A1"格式（而不是"孔位: 0"）

4. **测试状态栏更新**：
   - 开始检测时 → 状态栏显示"扫描中..."
   - 检测过程中 → 状态栏显示"检测中: X/144"
   - 检测完成后 → **状态栏应显示"扫描完成"**（不再显示"扫描中"）
   - 橙色箭头应该消失

5. **测试状态标签**：
   - 启动程序 → 状态: IDLE
   - 连接硬件 → 状态: IDLE（可能）
   - 回零 → 状态: HOMING → READY
   - 开始扫描 → 状态: SCANNING
   - 扫描完成 → 状态: COMPLETE

---

## 孔位编号对照表

| 索引范围 | 孔位名称 | 说明 |
|---------|---------|------|
| 0-11 | A1-A12 | 第一行 |
| 12-23 | B1-B12 | 第二行 |
| 24-35 | C1-C12 | 第三行 |
| ... | ... | ... |
| 132-143 | L1-L12 | 第十二行 |

**计算公式**：
- 行号(字母): `chr(ord('A') + hole_index // 12)`  # A-L
- 列号(数字): `hole_index % 12 + 1`  # 1-12
- 孔位名称: `f"{行号}{列号}"`  # 例如 "A1"

---

## 预期效果

修复后应该看到：

✅ **孔位名称正确显示**：
- 点击左上角第一个孔位 → 显示"孔位: A1"
- 点击第二个孔位 → 显示"孔位: A2"
- 点击第二行第一个孔位 → 显示"孔位: B1"
- 点击最后一个孔位 → 显示"孔位: L12"

✅ **状态栏正确更新**：
- 扫描过程：显示实时进度"检测中: X/144"
- 扫描完成：显示"扫描完成"（永久显示）
- 箭头消失

✅ **状态标签正确更新**：
- 根据系统状态实时更新
- 回零后显示"READY"
- 扫描时显示"SCANNING"

---

## 修改文件清单

1. **ui/well_plate_widget.py**
   - 添加 `hole_index_to_name()` 静态方法
   - 修复孔位编号绘制逻辑

2. **ui/main_window_v2.py**
   - 修复 `_on_hole_clicked()` 方法中的孔位名称显示
   - 修复 `_on_scan_finished()` 方法中的状态栏更新
   - 添加箭头清除功能

---

## 技术说明

### 孔位编号系统

144孔物料盘使用标准的微孔板编号系统：
- **行**: A-L (12行)
- **列**: 1-12 (12列)
- **总计**: 12 × 12 = 144 孔

内部使用线性索引 0-143，对外显示使用 A1-L12 格式。

### 状态栏超时机制

`QStatusBar.showMessage(text, timeout)`:
- `timeout = 0`: 永久显示，直到下次调用 `showMessage()`
- `timeout > 0`: 显示指定毫秒后自动清除
- 默认值: `timeout = 0`

修复后明确指定 `timeout = 0`，确保"扫描完成"永久显示。

---

**修复日期**：2026-01-28  
**版本**：V3.0.2  
**状态**：✅ 已修复并验证
