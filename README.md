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

当前暂无真实 CT 数据，因此系统内置模拟病例和模拟影像指标。后续可把 `backend/app/pipeline` 中的占位实现替换为真实 DICOM 读取、三维配准和 PyTorch 模型。

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

1. 进入病例总览页。
2. 打开任一肺结节随访病例。
3. 查看 T1/T2/T3 多期 CT 指标和模拟配准对比。
4. 选择目标结节并点击“运行目标结节分析”。
5. 查看 AI 风险评分、个性化随访建议、模型解释和版本追踪信息。
6. 生成结构化报告，编辑医生意见和随访计划，保存草稿或确认最终版。

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
- 模型训练标签：`nodules.csv` 可填写 `clinical_label` 与 `pathology_label`；训练样本至少需要 4 个带标签结节，并同时包含良性和恶性样本。
- 模型状态：前端侧边栏“模型状态”页面读取 `GET /model/status`、`GET /model/training/readiness`，显示权重文件、训练 artifact、`torch` / `onnxruntime` 依赖和当前推理模式。
- 模型训练：模型状态页可调用 `POST /model/training/run`，从当前队列的多期测量和结节标签训练/校准 `temporal_model.json`，并生成 `training_report.json`；推理优先级为 TorchScript、ONNX、JSON 模型、代理模型。
- 模型自检：模型状态页可调用 `POST /model/self-check`，使用内置三期 synthetic temporal fixture 校验 `temporal-nodule-v1` 输入 schema、输出契约，并执行真实模型或代理 fallback dry-run。
- 多结节分析：病例详情页可选择目标结节运行 `POST /analysis/{patient_id}/run?nodule_id=...`，每次分析结果记录 `nodule_id`，便于临床展示和回顾性研究表按结节追踪。
- 风险追踪：每次分析会在 `features_json.trace` 与 `research-table.csv` 中记录数据 schema、特征版本、模型版本、artifact/hash、推理时间和输入特征维度。
- 系统总览：前端侧边栏“系统总览”页面读取 `GET /system/status`，集中展示后端健康、数据规模、模型模式、导出能力、最近活动、七步功能成熟度和下一步行动建议。
- 报告确认：结构化报告页可调用 `PUT /reports/{report_id}` 保存医生编辑后的 Markdown、医生意见和随访建议，并可确认最终版；最终版默认锁定，支持后端 `.doc` 和打印 HTML 导出。
- 报告审计：`GET /reports/{report_id}/versions` 和 `GET /reports/{report_id}/audit` 可查看报告版本与操作记录；最终版需要修订时可调用 `POST /reports/{report_id}/revisions` 创建新草稿。
- DICOM 安全提示：上传 DICOM/zip 时会返回可用序列列表、选中序列 UID 和 PatientName/PatientID/AccessionNumber 等脱敏检查结果。

- 后端 smoke 检查：可运行 `cd backend && python smoke_check.py` 快速验证健康检查、导入预览/提交/批次/回滚、分析、报告版本/审计和系统状态。

## 后续扩展

- DICOM/NIfTI 真实读取：替换 `pipeline/preprocess.py`
- 结节分割与影像组学：扩展 `pipeline/features.py`
- ConvLSTM 模型训练与推理：替换 `pipeline/model.py`
- PDF/Word 报告导出：扩展 `routes/reports.py`
