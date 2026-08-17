# 楔形片表面瑕疵检测 — 深度学习技术指导（产业应用标准）

> 输入材料：`楔形片项目背景材料.pdf`(13p) / `数据集说明.pdf` / `标注规则.pdf` / `楔角片工程图纸.pdf`
> 数据：665 张 2048×2048 8bit BMP，暗场成像，labelme 6.3.1 多边形标注，4 类瑕疵
> 编写日期：2026-08-06

---

## 0. 先把结论说清楚

**你现在手上的不是一个"目标检测"任务，是一个"测量 + 判级"任务。**

工程图纸给的验收规范是**分区尺寸规范**，不是"有没有瑕疵"：

> 直径 Φ0.9 范围内：点子 <0.01，划痕宽度 <0.01，划痕长度 <0.3
> Φ0.9~Φ1.4 范围内：点子最大 <0.05；0.01~0.05 的点接受 3~5 个；<0.01 的点可接受
> Φ1.4~Φ2.2 范围内：按 40/20（MIL-PRF-13830B scratch-dig）
> 崩边：深度 <0.1，宽度 <0.1，且崩边不能影响到膜层，无锯齿状崩边

所以最终交付物是这条链，不是一个 `best.pt`：

```
原图 → ROI(有效孔径圆)定位 → 缺陷分割 → 亚像素尺寸测量(µm) → 按半径分区 → 查规范表 → OK/NG + 判定依据
```

**如果只训一个 YOLO 输出框和类别，产线是不能用的**——因为规范要的是「这个点子直径多少 µm、落在哪个区」，框的类别标签回答不了这个问题。这一点决定了后面所有的模型选型。

---

## 1. 成像链标定：先把 µm/pixel 钉死

背景材料 2.1 / 2.3 / 参数表三处互相矛盾，必须先解决，因为**整套判定规范都建立在 µm/pixel 上**。

自洽的一条链是（推荐采信）：

| 项 | 值 | 出处 |
|---|---|---|
| 相机 | HIKROBOT MV-CS040-A0UM，2048×2048 单色 | 2.3 |
| 像元 | 5.5 µm × 5.5 µm | 2.3 正文 |
| 物镜 | Olympus PlanN 4×，NA 0.16 | 2.3 |
| **物方分辨率** | **5.5 / 4 = 1.375 µm/pixel** | 2.3 计算 ✓ |
| 视场 | 2048 × 1.375 = 2816 µm ≈ 2.8 mm | 2.3 ✓ |
| 元件外径 | Φ2.6 mm → 2600/1.375 = **1891 px** | 图纸 |

1891 px 在 2048 px 画幅里占 92%，和样例图（圆形孔径几乎填满画面）完全吻合 → **这条链是对的，一张图 = 一片楔形片**。

需要修正的两处笔误（建议在材料里改掉，否则后续算法同学会踩）：

- **2.1 节**"5× 显微物镜 / NA0.15 / 1 µm 每像素 / FOV 2mm×2mm" —— 与 2.3 冲突，且 2mm FOV 装不下 Φ2.6mm 的元件。
- **2.3 参数表**"分辨率 4032×3036 / 像元 1.85µm" —— 这是另一款相机的参数（MV-CS040 是 4MP 2048×2048/5.5µm），与正文和实际数据集的 2048×2048 冲突。

> **动作项**：拿标准分划板（如 0.01mm 刻度尺）实测一次 µm/pixel 并写进配方，不要用理论值。畸变也要测——2.3 提到"平场设计保证 2048 范围内画质均匀"，但**边缘畸变会直接变成边缘区域的尺寸测量误差**，而崩边恰恰全在边缘。

### 1.1 关键尺度换算表（按 1.375 µm/px）

| 物理量 | µm | **像素** |
|---|---|---|
| 麻点典型尺寸 3~5 µm | 3~5 | **2.2 ~ 3.6 px** |
| 规范"点子 <0.01mm" | 10 | 7.3 px |
| 规范"点子 <0.05mm" | 50 | 36 px |
| 40/20 中 dig 20 = 0.2mm | 200 | 145 px |
| 40/20 中 scratch 40 ≈ 4µm 宽 | 4 | 2.9 px |
| 划痕宽 <0.01mm / 长 <0.3mm | 10 / 300 | 7.3 / 218 px |
| 崩边 深/宽 <0.1mm | 100 | 73 px |
| **分区半径** Φ0.9 / Φ1.4 / Φ2.2 | — | **r = 327 / 509 / 800 px** |

**这张表是整个方案的核心约束**：你要检的最小目标是 **2~4 个像素**。所有模型选型、切图策略、评价指标都必须围绕"2~4 px 目标"来设计。

---

## 2. 你现有 YOLO26X 方案的问题（必须改，否则一定失败）

那份 Colab 简介方向是对的（大图 + 小目标 + SAHI），但具体参数有几个**致命错误**：

| # | 问题 | 后果 | 修正 |
|---|---|---|---|
| 1 | **`imgsz=640` 直接喂 2048 原图** | 2048→640 缩放 3.2×，2~4px 的麻点变成 **0.7~1.2 px**，直接消失。Splash/Spot 共 3640 个实例（占 88%）全部报废 | **训练阶段就必须切图**，切片尺寸 = imgsz，**缩放比 1:1，绝不降采样** |
| 2 | **训练用整图、推理才用 SAHI** | 训练/推理尺度不一致，SAHI 救不回来。SAHI 是推理加速+召回补充，不是训练缺陷的补丁 | 训练切图 → 推理 SAHI，**两边切片参数一致** |
| 3 | 类别写成 scratch/pit/bubble/edge_chip | 与实际标注 splash/chipping/scratch/spot 不符 | 用实际 4 类 |
| 4 | `hsv_h=0.015, hsv_s=0.4` | **单色相机，无色彩通道**，这两个参数无意义 | 删除，只留 `hsv_v`（等价亮度扰动） |
| 5 | `mixup=0.15` | 暗场图两张叠加会**凭空造出不存在的散射点**，制造标签噪声 | **关掉（0.0）** |
| 6 | `erasing=0.2` | 随机擦除会**擦掉 3px 的麻点但标签还在** → 逼模型学幻觉 → 过杀飙升 | **关掉（0.0）** |
| 7 | `scale=0.5` | 允许缩放到 0.5×，3px 目标变 1.5px | 收紧到 `scale=0.15` |
| 8 | 用检测（box）而非分割 | labelme 是多边形，**丢掉多边形就丢掉了面积/长宽测量能力**，规范判不了 | 用 `-seg` 模型，保留 mask |
| 9 | 没有 ROI 掩膜 | 样例图里**圆环外是 SUS304 工装盘**，盘面有划痕/反光/孔洞纹理，是最大的过杀来源 | 先定位有效孔径圆，圆外一律屏蔽 |
| 10 | AGPL-3.0 | Ultralytics YOLO 系列是 AGPL-3.0，**产业化闭源交付必须买商业授权** | 见 §3.4 |

---

## 3. 模型选型

### 3.1 推荐架构：三通道并联 + 统一判级

单一模型吃不下"2px 麻点"和"73px 崩边"这个 30 倍的尺度跨度，也保证不了产业要求的零漏检。推荐这个结构：

```
                     ┌─ ROI 定位（有效孔径圆拟合）
                     │
        2048×2048 ───┼─→ [通道A] 实例分割模型（YOLO11x-seg / Mask R-CNN）
                     │       主责: chipping / scratch  （形状类，7~150 px）
                     │
                     ├─→ [通道B] 高召回点候选 + CNN 分类
                     │       主责: splash / spot        （点状类，2~10 px）
                     │       top-hat 形态学 → 候选点(召回≈100%) → 32×32 crop → 小CNN 四分类
                     │
                     └─→ [通道C] 无监督异常检测（EfficientAD / PatchCore）
                             主责: 4 类之外的未知缺陷，兜底防漏

              ↓ 融合去重（同一物理位置只报一次）
        亚像素测量(等效直径/长/宽, µm) → 半径分区 → 规范表 → OK/NG
```

**为什么点状类要单独走通道 B**：对 3px 的目标，检测器的框回归几乎无信息量（中心偏 1px，IoU 就从 1.0 掉到 0.3），而**形态学 top-hat 在暗场图上对亮点的召回本来就接近 100%**——暗场成像的物理本质就是"缺陷亮、背景黑"，这是这套光学系统白送的先验，不用可惜。把"找"交给物理先验、把"分"交给 CNN，是半导体/光学检测产业里的主流做法，比端到端检测器更容易压到零漏检。

标注规则里明写"splash 极易与 spot 混淆"——这正好说明**难点在分类不在定位**，架构应该顺着这个事实走。

### 3.2 各通道具体选型

**通道 A — 实例分割**

| 方案 | 优点 | 缺点 | 建议 |
|---|---|---|---|
| **YOLO11x-seg + P2 头** | 生态成熟、SAHI 现成、训练快 | AGPL；默认无 P2（stride 最小 8，对 2px 目标太粗） | **首选基线**，务必加 P2 头（stride 4） |
| YOLO26x-seg | STAL 小目标标签分配、NMS-free 端到端，方向对口 | 新，seg 权重可用性需确认；AGPL | 可作为 A/B 对照，**别当唯一方案** |
| **Cascade Mask R-CNN R50-FPN**（MMDetection） | **Apache-2.0，商用无授权风险**；小目标 AP 通常更高；anchor 可调到 4px | 慢 3~5× | **产业交付首选**，若节拍允许 |
| Mask2Former | mask 质量最好 | 训练重、小目标一般 | 不推荐 |

P2 头是这里最重要的单点改动：默认 YOLO 最细的特征图 stride=8，3px 的目标在特征图上不到半个格子；加上 stride=4 的 P2 层，小目标 AP 通常能涨 5~15 个点。

**通道 B — 点候选 + 分类**

- 候选：`白顶帽(top-hat, 半径 7~9px) → 局部对比度自适应阈值 → 连通域(面积 ≥2px)`，阈值调到**宁可 3000 个候选也不漏 1 个**
- 分类：ResNet18 / EfficientNet-B0，输入 32×32 或 48×48 灰度 crop，5 类（splash / spot / scratch / chipping / **背景**）
- 背景类样本从候选里挑没命中标注的，这一类是压过杀的关键

**通道 C — 无监督兜底**

- Anomalib 的 **EfficientAD**（快，适合在线）或 **PatchCore**（准，适合离线复核），**Apache-2.0**
- 只用 OK 品训练，在 tile 级别输出异常分数
- 作用：4 类之外的缺陷（气泡、膜层缺陷、崩角、异物）不会被静默漏掉，**这是产业验收的硬要求**

### 3.3 如果只做一版（资源受限时的最小可用方案）

`YOLO11x-seg + P2 头 + 640 切片训练 + SAHI 推理 + ROI 掩膜` —— 先把这条跑通拿到基线数字，再按 §6 的评估结果决定是否上通道 B/C。**不要一上来就三通道**。

### 3.4 许可证（产业化必须先想）

- **Ultralytics YOLOv8/11/26：AGPL-3.0**。闭源产品里用 = 必须开源你的全部服务端代码，或购买 Ultralytics Enterprise License（按年，联系官方报价）。
- **MMDetection / Detectron2 / Anomalib / OpenCV：Apache-2.0 / BSD**，商用无忧。
- 建议：**Colab 阶段用 YOLO 快速验证可行性，产业交付版切到 MMDetection**，或走完商业授权流程。这个决定越早做越省事。

---

## 4. 数据：现状体检与必须补的洞

### 4.1 现状

| 类别 | Train 原始 | Train 增强后 | Val | 判断 |
|---|---|---|---|---|
| Chipping | 1015 | 1015 | 208 | ✅ 够 |
| **Scratch** | **78** | 234 | **20** | 🔴 **严重不足** |
| Splash | 1872 | 1872 | 309 | ✅ 够 |
| Spot | 1768 | 1768 | 313 | ✅ 够 |

### 4.2 必须处理的 5 个问题

**① Scratch 只有 78 个训练实例 / 20 个验证实例 — 最大风险**

20 个实例的 val 上算 AP，95% 置信区间宽到 ±20 个点以上，**这个数字没有验收意义**。

- 短期：**5-fold 交叉验证**取均值±标准差，别用单一 val
- 中期：**必须补到 ≥300 个真实 scratch 实例**。手段：产线捞、人工制样（用标准划痕样板压制）、跨批次采集
- 增强只能缓解不能替代——78 个实例扩到 234 个，模型看到的仍是 78 种真实形态

**② 离线增强的数据泄露风险 — 立刻自查**

Scratch 78→234 是离线增强。**必须确认增强副本 100% 只在 train 集**。如果某张原图的增强版本进了 val，模型等于见过答案，AP 虚高，上产线原形毕露。

```bash
# 自查：val 里任何一张图的"原图基名"不得出现在 train 里
python - <<'EOF'
import re, pathlib
base = lambda p: re.sub(r'_(aug|rot|flip|copy)\d*$', '', p.stem)
tr = {base(p) for p in pathlib.Path('images/train').glob('*')}
va = {base(p) for p in pathlib.Path('images/val').glob('*')}
print("泄露样本:", tr & va or "无 ✅")
EOF
```

**③ 划分粒度：按"物理零件"而不是按"图"划分**

工装盘一次装 144 片（图纸：36×4=144）。如果同一片楔形片被拍了多张（不同波段/不同曝光/复检），这些图必须**整体在同一 split**。665 张图对应多少个物理零件？这个数字要查清楚——如果是 665 张 = 200 个零件 × 3 波段，那实际样本量只有 200，val 的独立性存疑。

**④ 缺 OK 样本 → 过杀率无法评估**

数据集说明只统计了缺陷实例数，**没有"完全无缺陷的 OK 图有多少张"**。没有 OK 图就**算不出过杀率（误判率）**，而过杀率是产业验收的两大指标之一。

> **动作项**：补采 ≥300 张确认 OK 的图（显微复检确认），单独建 `val_ok` 集，专门测过杀。

**⑤ splash / spot 标注一致性 — 建议做 κ 检验**

标注规则自己写着"splash 极易与 spot 混淆"，说明标签里必然有噪声。

- 抽 100 张让两名标注员独立重标，算 Cohen's κ
- **κ ≥ 0.75**：保持四分类
- **κ < 0.75**：训练时合并为超类 `dot`，推理后再用尺寸+亮度+边缘锐度做二次分级

工艺上这两类确实要分开（**脏污可以清洗后复检，麻点是永久损伤直接判废**），但如果人自己都分不清，逼模型分只会污染整个梯度。**先合并保住检出率，再单独优化分类头**，是更稳的路径。

顺带注意：图纸规范里"点子"是按**尺寸**判定的，不区分成因——所以即使 splash/spot 分错，**只要尺寸测准了，OK/NG 判定仍然正确**。这是这个方案的一个容错余量。

### 4.3 数据量目标

665 张对产业级验收偏少。参考量级：

| 阶段 | 图像数 | 每类最少实例 | 用途 |
|---|---|---|---|
| 现在 | 665 | scratch 78 🔴 | 可行性验证 |
| 试产 | ~2000 | ≥300 | 产线试跑 |
| 量产验收 | ≥5000（含 ≥1000 OK） | ≥500 | 正式验收 |

---

## 5. 训练实施（Colab）

### 5.1 硬件说明 — 先纠正一点

**你当前这台 Linux 是 VMware 虚拟机，显卡是 `VMware SVGA II Adapter`，没有 GPU 直通，`torch` 也没装。** 虚拟机里训不了。"本地 GPU"应该是在宿主机（Windows）上：

- 方案 1：宿主机装 **WSL2 + CUDA**，在 WSL2 里训（推荐，环境和 Linux 一致）
- 方案 2：宿主机 Windows 原生装 PyTorch CUDA
- 方案 3：给这台 VM 配 GPU 直通（VMware Workstation 支持有限，不推荐）

Colab 显存对照：

| GPU | 显存 | 建议配置 |
|---|---|---|
| A100 | 40GB | 1024 切片，YOLO11x-seg，batch 8 |
| L4 | 24GB | 1024 切片，YOLO11l-seg，batch 4；或 640 切片 batch 12 |
| T4（免费） | 16GB | 640 切片，YOLO11m/l-seg，batch 8，AMP |

### 5.2 数据准备：切图（最关键的一步）

**推荐参数**：切片 **1024×1024，重叠 256**（stride 768）→ 每张图 3×3 = **9 个切片**，训练 `imgsz=1024`，**缩放比 1:1**。

显存不够就退到 **640 切片 / 重叠 128**（stride 512）→ 4×4 = 16 切片，`imgsz=640`。640 切片下小目标的**相对**尺寸更大，对 splash/spot 反而更有利；代价是崩边/长划痕更容易被切断（靠重叠区兜）。

```python
# tools/wedge/tile_labelme.py —— labelme JSON + BMP → YOLO-seg 切片数据集
# 要点：1) 1:1 不缩放  2) 多边形按切片边界裁剪  3) 背景切片按比例保留  4) ROI 外丢弃
import json, cv2, numpy as np, pathlib
from shapely.geometry import Polygon, box

CLASSES = ["chipping", "scratch", "splash", "spot"]   # 顺序固定，写进 yaml
TILE, OVERLAP = 1024, 256
STRIDE = TILE - OVERLAP
BG_KEEP_RATIO = 0.15        # 无缺陷切片保留 15%，用于压过杀；全留会淹没正样本
MIN_AREA_KEEP = 0.35        # 多边形被切掉超过 65% 面积就丢弃该实例，避免残片标签

def find_roi(img):
    """拟合有效孔径圆 -> (cx, cy, r)。暗场下元件边缘是亮环，很好找。"""
    blur = cv2.GaussianBlur(img, (9, 9), 0)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.5, minDist=1000,
                               param1=100, param2=60, minRadius=800, maxRadius=1000)
    if circles is None:
        return None
    return circles[0][0]     # 实际项目建议改用亮环二值化 + cv2.fitEllipse，更稳

def tile_one(img_path, json_path, out_dir, split):
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    H, W = img.shape
    shapes = json.load(open(json_path, encoding="utf-8"))["shapes"]
    polys = [(CLASSES.index(s["label"]), Polygon(s["points"])) for s in shapes
             if s["label"] in CLASSES]
    roi = find_roi(img)

    xs = list(range(0, max(W - TILE, 0) + 1, STRIDE)) or [0]
    ys = list(range(0, max(H - TILE, 0) + 1, STRIDE)) or [0]
    if xs[-1] + TILE < W: xs.append(W - TILE)
    if ys[-1] + TILE < H: ys.append(H - TILE)

    for yi in ys:
        for xi in xs:
            # ROI 外的切片直接丢：圆外是 SUS304 工装盘，纹理是过杀主要来源
            if roi is not None:
                cx, cy, r = roi
                tcx, tcy = xi + TILE / 2, yi + TILE / 2
                if np.hypot(tcx - cx, tcy - cy) > r + TILE * 0.75:
                    continue

            cell = box(xi, yi, xi + TILE, yi + TILE)
            lines = []
            for cid, poly in polys:
                if not poly.intersects(cell):
                    continue
                clipped = poly.intersection(cell)
                if clipped.is_empty or clipped.area < poly.area * MIN_AREA_KEEP:
                    continue
                geoms = clipped.geoms if clipped.geom_type == "MultiPolygon" else [clipped]
                for g in geoms:
                    if g.area < 1:            # 小于 1px² 的碎片丢掉
                        continue
                    pts = np.array(g.exterior.coords)[:-1]
                    pts = (pts - [xi, yi]) / TILE          # YOLO-seg: 归一化多边形
                    pts = np.clip(pts, 0, 1)
                    lines.append(f"{cid} " + " ".join(f"{v:.6f}" for v in pts.ravel()))

            if not lines and np.random.rand() > BG_KEEP_RATIO:
                continue                                    # 背景切片按比例采样

            stem = f"{img_path.stem}_{xi}_{yi}"
            cv2.imwrite(str(out_dir / "images" / split / f"{stem}.png"),
                        img[yi:yi + TILE, xi:xi + TILE])     # PNG 无损，体积约为 BMP 的 1/3
            (out_dir / "labels" / split / f"{stem}.txt").write_text("\n".join(lines))
```

> ⚠️ 这份脚本是按材料写的骨架，**没有在真实数据上验证过**。落地前务必：
> ① 随机抽 20 个切片把 label 画回图上人眼核对；② 统计切片总数和各类实例数，与原始统计对账（重叠区会让实例数略增，属正常）。

**BMP → PNG**：665 张 2048² 8bit BMP ≈ 2.7GB，转 PNG 无损压缩后约 0.8~1GB，Colab 上传和 I/O 都快很多。**别转 JPG**——JPEG 的 8×8 块效应会直接毁掉 2~4px 的麻点。

### 5.3 Drive I/O

你那份简介里这条是对的，保留：**打包成一个 tar/zip 传 Drive，解压到 `/content/`**，绝不直接在 `/content/drive/` 挂载目录里逐文件读——Drive FUSE 的小文件随机读性能极差，能让训练慢 5~10 倍。

```bash
!mkdir -p /content/ds && tar -xf /content/drive/MyDrive/wedge_tiles.tar -C /content/ds
```

### 5.4 训练配置

```yaml
# /content/wedge.yaml
path: /content/ds
train: images/train
val: images/val
names:
  0: chipping
  1: scratch
  2: splash
  3: spot
```

```python
from ultralytics import YOLO

model = YOLO("yolo11x-seg.pt")     # 显存不足用 yolo11l-seg.pt
                                    # 加 P2 头见下方说明

model.train(
    data="/content/wedge.yaml",
    epochs=300, patience=60,
    imgsz=1024,                    # ★ 必须等于切片尺寸，1:1 不缩放
    batch=8, device=0, amp=True,
    rect=False, cache="disk",

    # ---- 增强：为"2~4px 暗场目标"定制 ----
    hsv_h=0.0, hsv_s=0.0,          # ★ 单色相机，无色彩通道
    hsv_v=0.30,                    # 亮度扰动保留：对抗光源衰减/曝光漂移，有物理意义
    degrees=180.0,                 # 元件圆对称，全角度旋转合法且有效
    fliplr=0.5, flipud=0.5,
    translate=0.10,
    scale=0.15,                    # ★ 从 0.5 收紧：0.5× 会把 3px 目标压到 1.5px
    shear=0.0, perspective=0.0,    # 显微成像近正交，透视变换是伪增强
    mosaic=1.0, close_mosaic=30,   # 最后 30 epoch 关 mosaic，让分布贴近真实推理
    mixup=0.0,                     # ★ 关：暗场叠图会造出不存在的散射点
    copy_paste=0.4,                # ★ 开：这是救 scratch(78实例) 的主力增强
    erasing=0.0,                   # ★ 关：会擦掉小目标但标签还在

    optimizer="AdamW", lr0=1e-3, cos_lr=True, warmup_epochs=5,
    box=7.5, cls=1.0, dfl=1.5,
    project="wedge", name="y11x_seg_p2_1024",
)
```

**加 P2 头**（对 2~4px 目标的最大单点收益）：复制 `ultralytics/cfg/models/11/yolo11-seg.yaml`，在 backbone 的 stride-4 层引出一路到 Detect/Segment 头，把 `[P3,P4,P5]` 改成 `[P2,P3,P4,P5]`。Ultralytics 官方仓库有 `yolov8-p2.yaml` 可直接照搬结构。代价是显存 +40%、速度 -30%。

**关于 `copy_paste=0.4`**：这是解决 scratch 样本荒最有效的手段——它把已有的 scratch mask 粘贴到其他图上。**前提是必须用 `-seg` 模型**（有 mask 才能 copy-paste），这也是第 8 条要求用分割的原因之一。

**关于 `degrees=180`**：元件是圆形、光源是环形，理论上旋转不变。但**环形光源如果装配有偏心，暗场散射会有方向性**——训练前抽几张图看看背景亮度是否各向同性，若有明显方向性则收到 `degrees=30` 并把偏心作为标定项修掉。

### 5.5 推理：SAHI 切片，参数必须与训练一致

```python
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction

m = AutoDetectionModel.from_pretrained(
    model_type="ultralytics",
    model_path="wedge/y11x_seg_p2_1024/weights/best.pt",
    confidence_threshold=0.15,     # ★ 产业场景先压低保召回，再用后处理压过杀
    device="cuda:0",
)

r = get_sliced_prediction(
    "part_0001.png",
    m,
    slice_height=1024, slice_width=1024,        # ★ 与训练切片一致
    overlap_height_ratio=0.25,                  # ★ 256/1024 = 0.25，与训练一致
    overlap_width_ratio=0.25,
    perform_standard_pred=False,                # ★ 关：整图预测会被缩放到 imgsz，小目标失真反成噪声源
    postprocess_type="NMM",                     # ★ 用 NMM 合并而非 NMS 丢弃：跨切片的长划痕要拼回一条
    postprocess_match_metric="IOS",
    postprocess_match_threshold=0.3,
)
```

三处与你原简介不同，都有明确理由：

- `perform_standard_pred=False` —— 整图那一路会被 resize 到 imgsz，正是问题 #1；开着只会污染结果。
- `NMM` + `IOS` —— 一条 218px 的划痕横跨两个切片会被切成两段，NMS 会**丢掉**其中一段，NMM 会**合并**成一条。测长度的任务里这是本质区别。
- `conf=0.15` —— 产业上先保召回，过杀交给下游几何/尺寸规则去压，比调高 conf 直接丢掉真缺陷安全得多。

---

## 6. 评价指标：mAP 不是验收标准

### 6.1 微小目标不能用 IoU 匹配

3px 的目标，预测框偏 1 个像素，IoU 就掉到 ~0.5；偏 1.5px 掉到 0.29 —— **mAP@0.5 会把一个定位得很好的检测判为漏检**。用 mAP 调参会把你引向完全错误的方向。

**匹配规则改为**：

| 类别 | 匹配准则 |
|---|---|
| splash / spot（点状） | **中心距 ≤ max(3 px, 0.5 × 等效直径)** |
| scratch（线状） | 中心线 Hausdorff 距离 ≤ 5 px，且长度误差 <20% |
| chipping（面状） | IoU ≥ 0.3（放宽，因边界本身标注一致性就不高） |

### 6.2 产业验收指标（这才是要写进验收报告的）

| 指标 | 定义 | 目标值 |
|---|---|---|
| **漏检率（逃逸率）** | 判 OK 但实际 NG 的零件 / 全部 NG 零件 | **0%**（超规范缺陷零漏检，硬指标） |
| **过杀率（误判率）** | 判 NG 但实际 OK 的零件 / 全部 OK 零件 | **< 3%**（试产期 <5%） |
| **尺寸测量误差** | 与显微复检比对，等效直径 | **\|Δd\| ≤ 1.4 µm（1 px）或 ±10%**，取大者 |
| **分区判定一致性** | 与人工判级结果一致率 | **> 98%** |
| **重复性** | 同一零件重复上下料 30 次，判定结果一致 | **> 99%** |
| **再现性 (Gauge R&R)** | 3 台设备 × 3 班次 × 10 零件 | **GRR < 10%** |
| **单片节拍** | 取图→出结果 | 按产线要求，见 §7 |

注意 **漏检率和过杀率是 trade-off**，靠调置信度阈值在 ROC 上滑动。产业上的标准做法是：**先把漏检钉死在 0，再在这个约束下最小化过杀**。所以验收报告里必须给的是 **"漏检=0 时的过杀率"** 这一个数，不是 mAP。

### 6.3 分区判级实现

```python
# tools/wedge/grade.py —— 把检测结果翻译成图纸判定
import numpy as np

UM_PER_PX = 1.375        # ★ 用实测标定值覆盖

# 图纸规范表（依 楔角片工程图纸.pdf 录入，落地前须与工艺确认）
ZONES = [
    # (外径mm, 点子最大µm, 该区允许的中等点数量上限, 划痕最大宽µm, 划痕最大长µm)
    (0.9,  10,  None, 10,  300),
    (1.4,  50,  5,    10,  300),   # 0.01~0.05 的点接受 3~5 个
    (2.2,  200, None, 4,   None),  # 40/20: dig20=0.2mm, scratch40≈4µm 宽
]

def grade(defects, center_px, um_per_px=UM_PER_PX):
    """defects: [{'cls','mask'(bool 2D),'cx','cy'}, ...] -> (是否OK, 判定明细)"""
    reasons, mid_count = [], {0.9: 0, 1.4: 0, 2.2: 0}

    for d in defects:
        r_mm = np.hypot(d["cx"] - center_px[0], d["cy"] - center_px[1]) * um_per_px / 1000 * 2
        zone = next((z for z in ZONES if r_mm <= z[0]), None)
        if zone is None:
            continue                                    # 有效孔径外，不判
        outer, dot_max, mid_max, sc_w_max, sc_l_max = zone

        area_px = int(d["mask"].sum())
        d_eq = 2 * np.sqrt(area_px / np.pi) * um_per_px  # 等效圆直径 µm

        if d["cls"] in ("splash", "spot"):
            if d_eq >= dot_max:
                reasons.append(f"NG 点子 Φ{d_eq:.1f}µm ≥ {dot_max}µm @ 区{outer}mm")
            elif mid_max is not None and d_eq >= 10:
                mid_count[outer] += 1
        elif d["cls"] == "scratch":
            w_um, l_um = measure_线宽与长度(d["mask"], um_per_px)   # 骨架化后测
            if w_um >= sc_w_max:
                reasons.append(f"NG 划痕宽 {w_um:.1f}µm @ 区{outer}mm")
            if sc_l_max and l_um >= sc_l_max:
                reasons.append(f"NG 划痕长 {l_um:.1f}µm @ 区{outer}mm")
        elif d["cls"] == "chipping":
            w_um, dep_um = measure_崩边(d["mask"], um_per_px)
            if w_um >= 100 or dep_um >= 100:
                reasons.append(f"NG 崩边 {w_um:.0f}×{dep_um:.0f}µm")

    for outer, n in mid_count.items():
        if n > 5:
            reasons.append(f"NG 中等点子 {n} 个 > 5 @ 区{outer}mm")

    return (len(reasons) == 0), reasons
```

**测量精度提示**：3px 的目标直接数像素，量化误差就有 ±30%。要达到 §6.2 的 ±10%，必须做**亚像素测量**——对灰度做二维高斯拟合取等效直径，或用亚像素边缘（Zernike 矩 / 灰度重心法），而不是数二值 mask 的像素个数。这一步在验收里权重很高，别省。

---

## 7. 产业部署

### 7.1 节拍估算

工装盘 144 片。假设 YOLO11x-seg@1024 在 RTX 4090 TensorRT FP16 下约 **12 ms/切片**：

```
ROI 内有效切片 ≈ 7 个/片  →  7 × 12 = 84 ms
+ 通道B(形态学+CNN)      ≈  25 ms
+ 测量与判级             ≈  10 ms
────────────────────────────────────
单片推理 ≈ 120 ms  →  144 片 ≈ 17.3 s（不含运动与对焦时间）
```

**运动+对焦通常才是瓶颈**，不是推理。所以：

- 先确认产线要求的**盘节拍**，倒推单片预算，再决定模型规模（x / l / m）
- 相机 90.1 fps，采图不是瓶颈；**推理和运动要流水线并行**（采第 N+1 片时算第 N 片）—— 这正好落在 DAC-3D 的 `scan_service` 里

### 7.2 集成到 DAC-3D 架构

按 `CLAUDE.md` 的五层架构，模型推理属于 **Layer 3 服务层**：

```
dac3d/services/defect_service.py     # 现有：形态学算法 → 保留为通道B的候选生成
dac3d/services/dl_infer_service.py   # 新增：ONNX/TensorRT 推理封装
dac3d/services/grading_service.py    # 新增：尺寸测量 + 分区判级
configs/recipes/wedge_op22.yaml      # 新增：配方（模型路径/阈值/µm-per-px/规范表）
```

**必须遵守的架构底线**（`docs/dac3d-product-strategy.md` 第 6 节）：

- **规范表、阈值、µm/pixel、ROI 参数全部写进配方**，不写死在代码里。换一款元件（不同直径、不同规范）= 换一份配方，不改代码。
- 模型文件按配方引用并带版本号，`defect_service` 不感知具体是 YOLO 还是 MMDet —— 定义 `IDefectDetector` 接口，两种实现都实装，符合"每个真实驱动都要有 sim 仿真驱动"的规范（sim 版返回固定结果供无 GPU 开发）。
- 触发核不碰这些：推理是纯软件域，与 FPGA 触发时序解耦。

### 7.3 上线必需的工程配套

| 项 | 内容 |
|---|---|
| **模型格式** | PyTorch → ONNX → TensorRT FP16。**导出后必须逐张比对 FP32/FP16 输出**——2px 目标对数值精度敏感，FP16 可能掉召回 |
| **每班标定** | 材料 2.1 已有三步流程（暗场校正 / 平场校正 / 双波长配准），**必须固化为开机自检**，标定不通过禁止生产 |
| **漂移监控** | 每班跑标准样板（已知缺陷的金标样片），判定结果偏移即报警 |
| **数据回流** | 所有 NG 图 + 5% 随机 OK 图存档，季度重训。这是长期精度的唯一来源 |
| **模型版本追溯** | 每个判定结果记录：模型 hash、配方版本、标定时间戳、原图路径。质量追溯的法定要求 |
| **人工复判闭环** | NG 品进复判工位，复判结果回写数据库 → 自动统计真实漏检/过杀 → 这是唯一可信的现场指标来源 |

---

## 8. 执行路线

| 阶段 | 时长 | 交付 | 门槛 |
|---|---|---|---|
| **P0 数据体检** | 3 天 | 泄露自查报告 / κ 检验 / 零件级划分 / OK 图数量确认 | §4.2 五个问题全部有明确结论 |
| **P1 标定与 ROI** | 3 天 | 实测 µm/px、畸变图、ROI 圆拟合模块（成功率 >99.5%） | ROI 定位在 665 张上全部正确 |
| **P2 切片与基线** | 1 周 | 切片数据集 + YOLO11x-seg 基线（先不加 P2 头） | 跑通，拿到第一组数字 |
| **P3 小目标优化** | 2 周 | +P2 头、增强调优、SAHI 推理、5-fold CV | splash/spot 召回 >95% |
| **P4 测量与判级** | 2 周 | 亚像素测量 + 分区判级 + 与人工判级比对 | 判定一致性 >98% |
| **P5 补数据** | 并行 | scratch ≥300 实例、OK 图 ≥300 张 | — |
| **P6 兜底通道** | 1 周 | Anomalib EfficientAD 未知缺陷通道 | 已知缺陷之外有告警能力 |
| **P7 部署** | 2 周 | TensorRT + 集成 dac3d + 节拍实测 | 满足产线节拍 |
| **P8 验收** | 1 周 | 漏检=0 时的过杀率、Gauge R&R、重复性 | §6.2 全部指标达标 |

**P0 是硬前置**。数据泄露没查清就开始训，后面所有数字都是假的，越往后返工代价越大。

---

## 9. 一句话总结

> 用 **YOLO11x-seg + P2 头**、**1024 原分辨率切片训练**（不是缩放到 640）、**ROI 圆内掩膜**、**SAHI+NMM 推理** 做基线；
> 点状缺陷（占 88% 实例）另开 **形态学高召回候选 + 小 CNN 分类** 通道；
> 再加 **Anomalib** 兜未知缺陷；
> 最后接 **亚像素测量 + 图纸分区判级**——因为验收标准是"点子多少 µm、在哪个区"，不是 mAP。
>
> 开工前必须先解决：**scratch 只有 78 个实例**、**离线增强可能泄露**、**没有 OK 样本导致过杀率无法评估** 这三件事。

---

## 附：待确认清单

以下几项来自材料 OCR 与推断，落地前请与工艺/光学确认：

1. 图纸规范数值（0.01 / 0.05 / 0.3 / 40-20 / 崩边 0.1）的准确读数与单位
2. 665 张图对应多少个**物理零件**、是否含多波段重复拍摄
3. OK（无缺陷）图像数量
4. 数据集是否已是 YOLO 格式，还是仍为 labelme JSON
5. 产线要求的**盘节拍**（秒/144 片）
6. 交付形态是否闭源 → 决定 §3.4 的许可证路线
7. 材料 2.3 提到的三波段（紫外/绿/黄）系统：**当前 665 张是单波段还是三波段？** 若已有三波段配准图像，可把三通道当作 RGB 输入直接送模型，通常能再涨几个点——但这会改变整个数据管线，需尽早确认
