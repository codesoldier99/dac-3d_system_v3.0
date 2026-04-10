# 实验室数据集管理指南（光学瑕疵检测）

> 目标读者：实验室两位负责人（教授）与团队全体研究生

## 版本信息
- 文档版本：v1.0
- 创建者：自动提交（由 GitHub Copilot Chat 助手代为创建）
- 仓库：codesoldier99/dac-3d_system_v3.0
- 路径：docs/dataset-management-guide.md

## 目录
1. 概述
2. 适用对象与约定
3. 总体架构与工具选型
4. DVC（Data Version Control）详解与配置示例
5. 云存储选型与私有部署建议
6. 数据目录结构与命名规范
7. 标注管理与标注格式
8. 元数据、版本与划分规范示例
9. 团队协作与权限管理（GitHub 组织与流程）
10. 快速启动命令清单
11. 常见问题与注意事项
12. 附录：示例配置片段与 YAML 模板

---

## 1. 概述
本指南面向实验室光学瑕疵检测项目，覆盖滤光片、楔型片、手机镜头球面镜片等图像数据的采集、保存、标注、版本控制、共享与安全管理。目标是建立可复现、可审计、便于协作的数据管理体系，支持多名研究生并行工作并由两位教授共同监督。

## 2. 适用对象与约定
- 主管：两位教授（仓库 Owners）。
- 数据管理员（Maintainers）：建议由 1-2 名高年级研究生担任，负责审核标注与合并 PR。
- 普通研究生（Members）：负责数据采集与标注，提交 PR 或通过 DVC 上传数据。
- 术语约定：raw = 原始未改动数据；annotated = 标注后的数据；processed = 预处理或训练输入。

## 3. 总体架构与工具选型
推荐组合：
- 代码管理：Git + GitHub（仓库已存在）
- 数据版本与流水线：DVC（Data Version Control）
- 数据存储（真实二进制数据）：云存储（阿里云 OSS / 腾讯 COS）或实验室私有 MinIO
- 标注工具：Label Studio（开源，支持自托管）或 Roboflow（付费/托管）
- 实验追踪：MLflow 或 Weights & Biases（W&B）
- 文档与协作：GitHub Wiki / docs 目录 / 飞书或企业微信

理由：DVC 与 Git 无缝集成，可将数据指针纳入 Git 管理，支持大文件与远程存储；MinIO 可在实验室服务器内部署，保障数据不外泄。

## 4. DVC 详解与配置示例
1) 为什么 DVC：
- 将大文件（图像、二进制）从 Git 中分离，保存指针到 Git，避免仓库膨胀。
- 支持可重现的 pipeline（dvc.yaml），记录数据和模型依赖。

2) 安装（示例）
```bash
pip install dvc
# 如果使用阿里云 OSS 或 腾讯 COS，请安装相应扩展，例如 dvc-oss
pip install 'dvc[oss]'
```

3) 初始化 DVC（在仓库根目录）
```bash
git checkout -b add-dataset-management-guide
dvc init
git commit -m "chore: dvc init"
```

4) 配置远程（示例：MinIO）
```bash
# 设置一个名为 myremote 的 dvc 远程
# MinIO 示例（私有部署）
dvc remote add -d myremote s3://lab-datasets
# 配置凭证（安全地在 CI/Secrets 或本地 .dvc/config 中设置）
dvc remote modify myremote endpointurl http://minio.lab.internal:9000
# 如果使用阿里云 OSS，配置格式会不同，可参考 dvc-oss 文档
```

5) 添加数据并推送
```bash
dvc add dataset/raw/optical_filter
git add dataset/raw/optical_filter.dvc dataset/.gitignore
git commit -m "Add raw optical_filter dataset (dvc)"
dvc push
```

6) 拉取数据（其他成员）
```bash
git clone https://github.com/codesoldier99/dac-3d_system_v3.0.git
git checkout add-dataset-management-guide
dvc pull
```

7) 使用 dvc.yaml 管理数据处理流水线（示例）
```yaml
stages:
  preprocess:
    cmd: python src/preprocess.py data/raw data/processed
    deps:
      - src/preprocess.py
      - data/raw
    outs:
      - data/processed
```

## 5. 云存储选型与私有部署建议
- 实验室有服务器：优先部署 MinIO（S3 兼容），优点：免费、数据留在内网、可控制访问。
- 无自有服务器：使用阿里云 OSS 或腾讯 COS，国内访问速度快，稳定性高。
- 安全建议：开启访问凭证生命周期管理，使用项目级或团队级 IAM 权限，只在 CI 中使用最小权限的密钥，定期轮换密钥。

## 6. 数据目录结构与命名规范
示例目录结构（仓库中只保留小样或指针，真实数据由 DVC 远程存储）

```
dataset/
├── raw/
│   ├── optical_filter/
│   │   ├── 2024-09-01_batch01/
│   │   └── 2025-03-15_batch02/
│   ├── wedge_optics/
│   └── phone_lens/
├── annotated/
│   ├── optical_filter/
│   │   ├── images/
│   │   ├── labels/         # YOLO 或 COCO
│   │   └── annotations.json
├── processed/
│   ├── train/
│   ├── val/
│   └── test/
└── metadata/
    ├── dataset_info.yaml
    ├── label_map.yaml
    └── split_record.csv
```

命名规范建议：
- 批次采用 YYYY-MM-DD_batchNN 格式
- 图片文件名保留来源与编号，例如 optical_filter_20250315_000123.jpg
- 标注文件统一使用 COCO 或 YOLO 格式，实验室内部统一为一种

## 7. 标注管理与标注格式
推荐工具：Label Studio（自托管）或 Roboflow。

标注流程建议：
1. 研究生在 own 分支或 fork 上添加标注样本（或直接在标注系统中提交）
2. 数据管理员（高年级）进行抽样审核，发现问题提交 issue 并打回修正
3. 审核通过后，标注结果导出（COCO/YOLO）并提交到 annotated 目录，通过 DVC 管理并 push

标注格式示例（label_map.yaml）：
```yaml
labels:
  - id: 0
    name: scratch
  - id: 1
    name: bubble
  - id: 2
    name: dust
  - id: 3
    name: crack
```

## 8. 元数据、版本与划分规范示例
dataset_info.yaml（样例）
```yaml
dataset_name: optical-defect-v2.1
created_by: 张三
date: 2025-10-01
product_type: optical_filter
defect_categories:
  - scratch
  - bubble
  - dust
  - crack
total_images: 5000
annotation_tool: Label Studio
annotation_reviewed_by: 王教授
split:
  train: 0.7
  val: 0.15
  test: 0.15
notes: |
  - 原始数据未经增强
  - 部分图像存在重影或光照不均
```

数据划分建议：按批次或按采集时间分层抽样，保证 train/val/test 中各类瑕疵分布一致。

## 9. 团队协作与权限管理（GitHub 组织与工作流）
仓库建议加入 GitHub Organization，成员角色如下：
- Owners：两位教授（您与另一位教授）
- Maintainers：1-2 名高年级研究生（负责审核、合并 PR、管理 DVC 远程）
- Members：其它研究生（普通贡献者）

工作流建议（代码与数据变更）：
- 所有变更通过分支与 PR 流程进行（包括数据指针的变更）
- 添加或更新数据集：研究生在个人分支上 dvc add -> 提交 .dvc 文件 -> 发起 PR -> Maintainer 审核 -> 合并 -> Maintainer 执行 dvc push（或者 CI 自动执行）
- 审核标准：数据文件命名、metadata 完整、标注格式正确、通过随机抽样检查质量

分支保护建议：
- 保护 main 分支，要求至少 1 个 Maintainer 审核通过
- 强制通过 CI（例如简单的 dvc pull 测试或 lint）

## 10. 快速启动命令清单
安装：
```bash
pip install dvc
# 根据后端选择安装扩展
pip install 'dvc[oss]'
```
初始化与远程配置：
```bash
git clone https://github.com/codesoldier99/dac-3d_system_v3.0.git
cd dac-3d_system_v3.0
git checkout -b add-dataset-management-guide
# 本地初始化 dvc（若仓库尚未初始化）
dvc init
# 添加远程（示例）
dvc remote add -d myremote s3://lab-datasets
```
添加并推送数据：
```bash
dvc add dataset/raw/optical_filter
git add dataset/raw/optical_filter.dvc dataset/.gitignore
git commit -m "Add raw optical_filter dataset (dvc)"
dvc push
```
拉取：
```bash
dvc pull
```

## 11. 常见问题与注意事项
- 不要把大文件直接推到 Git（会导致仓库体积膨胀）
- DVC 的远程凭证请勿提交到仓库，使用 CI Secrets 或实验室安全存储
- 数据敏感性：若涉及隐私或商业机密，优先使用私有部署（MinIO）并开启访问控制
- 标注一致性：定义明确的 label_map 与标注规范，必要时组织培训

## 12. 附录：示例配置与模板
1) dvc remote（MinIO）示例
```bash
dvc remote add -d myremote s3://lab-datasets
dvc remote modify myremote endpointurl http://minio.lab.internal:9000
dvc remote modify myremote access_key_id <ACCESS_KEY>
dvc remote modify myremote secret_access_key <SECRET_KEY>
```

2) dataset_info.yaml 模板（复制到 dataset/metadata/dataset_info.yaml）
```yaml
# 模板
dataset_name: <dataset_name>
created_by: <人名>
date: <YYYY-MM-DD>
product_type: <optical_filter|wedge|phone_lens>
defect_categories: []
total_images: 0
annotation_tool: <Label Studio | Roboflow>
annotation_reviewed_by: <姓名>
split:
  train: 0.7
  val: 0.15
  test: 0.15
notes: |
  <补充说明>
```

3) label_map.yaml 样例
```yaml
labels:
  - id: 0
    name: scratch
  - id: 1
    name: bubble
```

---
