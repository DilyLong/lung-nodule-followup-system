# Lung Nodule Follow-up System

本地网页 MVP：肺结节多期 CT 时序特征提取、风险评估与个性化随访辅助决策系统。

## 当前版本定位

第一版用于演示和继续开发：

- 病例管理与临床工作台
- 多结节管理与目标结节独立时序风险分析
- 肺结节直径、体积、密度、实性成分等动态指标展示
- 三维配准、时序特征、ConvLSTM 推理的可替换算法接口
- AI 风险分层与个体化随访建议
- 结构化随访报告生成、医生编辑确认与草稿/最终版保存
- 真实 CSV 队列校验、预览、质控评分、批次审计与一键导入/回滚
- 数据集规范页面，展示真实 DICOM 多期目录、CSV 字段、标签枚举和质控规则
- 研究导出：基础队列表、测量表、分析研究表 CSV 与研究数据包 ZIP
- 报告版本和审计记录，最终版锁定后可创建修订草稿
- 模型接入状态页，检查 `.pt` / `.onnx` 权重、队列训练 JSON 模型、推理依赖、当前真实/代理模型模式，并支持模型输入 schema、dry-run 推理自检和队列训练 readiness/run。
- 系统状态总览页，集中展示后端健康、数据规模、模型状态、导出能力和功能成熟度
- 演示流程控制台，一键重置并预生成代表病例分析/报告，展示可讲解的临床故事线
- 训练结果解释页，展示 AUC、Accuracy、Sensitivity、Specificity、Brier Score、校准分箱和训练样本列表
- 报告导出增强，Word/打印 HTML 包含封面、风险摘要、医生签名区和草稿/最终版水印

> 安全边界：当前系统仅用于本地科研演示和继续开发；synthetic demo cohort 不是真实患者数据，AI 风险评分不能直接作为临床诊疗依据，真实 DICOM 上传前必须完成脱敏。

当前暂无真实 CT 数据，因此系统内置模拟病例和模拟影像指标。后续可把 `backend/app/pipeline` 中的占位实现替换为真实 DICOM 读取、三维配准和 PyTorch 模型。

## 当前完成度

| 模块 | 状态 | 说明 |
|---|---|---|
| 多期随访工作台 | 可演示 | 支持病例、检查、结节、测量和目标结节独立分析。 |
| Synthetic demo cohort | 可演示 | 12 例病例、16 个结节、48 条多期测量，含训练标签和代表故事线。 |
| 真实 CSV 导入治理 | 可演示 | 支持校验、预览、质控评分、批次审计、实体明细和回滚。 |
| DICOM 上传与浏览 | MVP | 支持脱敏提示、序列信息、窗宽窗位和 ROI 标注生成测量。 |
| 模型训练闭环 | 研究原型 | 支持 JSON 校准模型训练、校准分箱、样本列表和 dry-run 自检。 |
| 报告确认与导出 | 可演示 | 支持版本审计、最终版锁定、修订草稿、Word/打印 HTML 导出。 |
| 真实深度模型 | 待接入 | 可替换 TorchScript/ONNX/PyTorch 权重。 |
| 真实三维分割/配准 | 待升级 | 当前为 MVP 接口和可解释代理实现。 |

## 演示截图占位

- `docs/screenshots/demo-walkthrough.png`：演示流程控制台。
- `docs/screenshots/model-status.png`：模型状态与训练解释页。
- `docs/screenshots/patient-detail.png`：代表病例详情和目标结节分析。
- `docs/screenshots/report-export.png`：结构化报告与导出预览。


## 目录结构

```text
backend/   FastAPI 后端、SQLite 数据库、算法管线接口
frontend/  React + Vite 前端临床工作台
```

## 后端运行

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

首次启动会自动创建 SQLite 数据库并写入演示病例。

API 文档：<http://127.0.0.1:8000/docs>

## 前端运行

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：<http://127.0.0.1:5173>

## 演示流程

0. 进入侧边栏“演示流程”，点击“开始标准演示”，系统会自动 reset synthetic demo 状态并 prepare 代表病例。
1. 在演示流程页查看状态卡片：训练是否完成、代表病例报告是否生成、最近报告 ID。
2. 按推荐点击顺序进入“系统总览”，查看数据质量看板、最近分析和最近报告。
3. 进入“模型状态”，运行队列训练和模型自检，讲解 AUC、Accuracy、Sensitivity、Specificity、Brier Score、校准分箱和训练样本列表。
4. 打开代表病例故事线：高风险进展、稳定纯磨玻璃、炎性缩小、多发结节差异化随访。
5. 在病例详情页选择目标结节并点击“运行目标结节分析”。
6. 查看 AI 风险评分、个性化随访建议、模型解释和版本追踪信息。
7. 生成结构化报告，填入医生意见/随访计划模板，保存草稿或确认最终版。
8. 导出 Word 或打印 HTML，报告包含封面、风险摘要、医生签名区和草稿/最终版水印。

## 代表病例故事线

| 病例 | 故事线 | 适合展示 |
|---|---|---|
| `SYN-LN-2026-004` | 高风险进展病例 | 实性结节快速增大、高风险评分、短间隔复查和 MDT 建议。 |
| `SYN-LN-2026-011` | 稳定纯磨玻璃病例 | 多发纯磨玻璃长期稳定、低风险随访、避免过度干预。 |
| `SYN-LN-2026-008` | 炎性缩小病例 | 结节逐渐缩小、动态变化降低风险分层。 |
| `SYN-LN-2026-009` | 多发结节差异化随访病例 | 同一患者不同结节风险不同，需要目标结节独立分析。 |

## 主要 API Endpoint

| 模块 | Endpoint | 用途 |
|---|---|---|
| 健康检查 | `GET /health` | 后端连通性检查。 |
| 病例 | `GET /patients`、`GET /patients/{patient_id}` | 病例列表和详情。 |
| 分析 | `POST /analysis/{patient_id}/run?nodule_id=...` | 运行目标结节独立时序风险分析。 |
| 报告 | `POST /reports/{analysis_id}`、`PUT /reports/{report_id}` | 生成、编辑、保存和最终确认报告。 |
| 报告导出 | `GET /reports/{report_id}/export.doc`、`GET /reports/{report_id}/print.html` | 导出 Word 或打印 HTML。 |
| 报告审计 | `GET /reports/{report_id}/versions`、`GET /reports/{report_id}/audit` | 查看版本和审计记录。 |
| Demo | `GET /demo/walkthrough`、`GET /demo/representative-cases` | 演示脚本、状态卡片、安全提示和代表病例故事线。 |
| Demo 控制 | `POST /demo/reset`、`POST /demo/prepare` | 重置 synthetic demo 状态并预生成训练/分析/报告。 |
| 模型状态 | `GET /model/status`、`POST /model/self-check` | 模型 artifact、依赖、自检和 dry-run。 |
| 模型训练 | `GET /model/training/readiness`、`POST /model/training/run`、`POST /model/training/demo-cohort` | 队列训练、校准报告和 synthetic cohort 重载。 |
| 数据导入 | `GET /imports/spec`、`POST /imports/validate`、`POST /imports/preview`、`POST /imports/commit` | 数据集规范、CSV 校验、预览和导入。 |
| 导入治理 | `GET /imports/batches`、`GET /imports/batches/{batch_id}`、`POST /imports/batches/{batch_id}/rollback` | 批次审计和回滚。 |
| 研究导出 | `GET /exports/cohort-table.csv`、`GET /exports/measurements.csv`、`GET /exports/research-table.csv`、`GET /exports/research-package.zip` | 队列表、测量表、研究表和 ZIP 数据包。 |

## 真实数据与模型接入准备

- 数据集规范：前端侧边栏“数据集规范”页面读取 `GET /imports/spec`，展示 DICOM 目录、CSV 文件、标签枚举和质控规则。
- CSV 导入校验：在“影像上传”页上传 `patients.csv`、`studies.csv`、`nodules.csv`、`measurements.csv`，系统先做规范校验并返回报告。
- CSV 导入预览：`POST /imports/preview` 会返回新增/更新数量、质控分、随访完整性、日期间隔和 DICOM 路径关联提示。
- CSV 一键入库：校验和预览通过后可调用 `POST /imports/commit` 写入患者、检查、结节和测量数据；重复患者/检查/结节/测量会按稳定键更新。
- 导入批次治理：`GET /imports/batches`、`GET /imports/batches/{batch_id}` 可查看批次和实体明细；`POST /imports/batches/{batch_id}/rollback` 可回滚已提交批次。
- 测量来源追踪：测量记录区分 `demo`、`radiologist_report`、`imported_research_table`、`manual_annotation`、`roi_dicom` 等来源，并同步到随访点和测量表导出。
- CSV 导出：总览页和病例详情页可下载 `cohort-table.csv`、`measurements.csv`、`research-table.csv`；其中 `cohort-table.csv` 不依赖 AI 分析结果，并保留结节维度的最新风险评分。
- 研究数据包：总览页和病例详情页可下载 `research-package.zip`，内含三张 CSV、`imports-spec.json`、`model-status.json` 和 `metadata.json`。
- 模型 artifact：将 TorchScript `temporal_model.pt` 或 ONNX `temporal_model.onnx` 放入 `backend/model_artifacts/`；TorchScript 需要安装 `torch`，ONNX 需要安装 `onnxruntime`。也可在模型状态页基于带标签队列生成 `temporal_model.json`，作为本地校准后的表格风险模型。
- Demo 控制台：侧边栏“演示流程”页面读取 `GET /demo/walkthrough`，提供 8 分钟演示脚本，并可调用 `POST /demo/reset` 清理 synthetic 分析/报告/训练 artifact、调用 `POST /demo/prepare` 预生成代表病例分析和草稿报告。
- Synthetic demo cohort：首次启动自动写入 12 个模拟患者、16 个结节和 48 条多期随访测量，包含良恶性训练标签，可在无真实数据时演示训练闭环。
- 训练演示模式：模型状态页可调用 `POST /model/training/demo-cohort` 重载 synthetic demo cohort，再运行 readiness/run 完成 JSON 模型训练演示。
- 模型训练标签：`nodules.csv` 可填写 `clinical_label` 与 `pathology_label`；训练样本至少需要 4 个带标签结节，并同时包含良性和恶性样本。
- 模型状态：前端侧边栏“模型状态”页面读取 `GET /model/status`、`GET /model/training/readiness`，显示权重文件、训练 artifact、`torch` / `onnxruntime` 依赖和当前推理模式。
- 模型训练：模型状态页可调用 `POST /model/training/run`，从当前队列的多期测量和结节标签训练/校准 `temporal_model.json`，并生成 `training_report.json`；推理优先级为 TorchScript、ONNX、JSON 模型、代理模型。
- 模型自检：模型状态页可调用 `POST /model/self-check`，使用内置三期 synthetic temporal fixture 校验 `temporal-nodule-v1` 输入 schema、输出契约，并执行真实模型或代理 fallback dry-run。
- 多结节分析：病例详情页可选择目标结节运行 `POST /analysis/{patient_id}/run?nodule_id=...`，每次分析结果记录 `nodule_id`，便于临床展示和回顾性研究表按结节追踪。
- 风险追踪：每次分析会在 `features_json.trace` 与 `research-table.csv` 中记录数据 schema、特征版本、模型版本、artifact/hash、推理时间和输入特征维度。
- 系统总览：前端侧边栏“系统总览”页面读取 `GET /system/status`，集中展示后端健康、数据规模、模型模式、导出能力、数据质量看板、最近活动、功能成熟度和下一步行动建议。
- 报告确认：结构化报告页可调用 `PUT /reports/{report_id}` 保存医生编辑后的 Markdown、医生意见和随访建议；报告模板包含医生确认清单、随访间隔和指南参考，前端提供医生意见/随访计划模板填充；最终版默认锁定，支持后端 `.doc` 和打印 HTML 导出。
- 报告审计：`GET /reports/{report_id}/versions` 和 `GET /reports/{report_id}/audit` 可查看报告版本与操作记录；最终版需要修订时可调用 `POST /reports/{report_id}/revisions` 创建新草稿。
- DICOM 安全提示：上传 DICOM/zip 时会返回可用序列列表、选中序列 UID 和 PatientName/PatientID/AccessionNumber 等脱敏检查结果。
- 影像浏览体验：DICOM 浏览器支持肺窗、纵隔窗、骨窗和结节增强预设，保留手动窗宽窗位调节，并支持编辑既有 ROI 标注后重新生成测量。

- 后端 smoke 检查：可运行 `cd backend && python smoke_check.py` 快速验证健康检查、导入预览/提交/批次/回滚、分析、报告版本/审计和系统状态。

## Roadmap

1. 接入真实匿名化多期 CT 队列，完善导入质控和训练/验证集拆分。
2. 用 SimpleITK/ANTs 升级肺部配准、肺野分割和结节坐标映射。
3. 接入 PyTorch/ONNX 时序模型权重，替换当前 JSON/代理模型。
4. 增加结节分割、影像组学特征和多模态临床变量融合。
5. 把 smoke 检查拆分为 pytest，覆盖 demo、训练、报告、导入和系统状态。
6. 增加受控的 PDF 导出、截图文档和真实演示数据脱敏流程。
