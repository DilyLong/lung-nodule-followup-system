# Lung Nodule Follow-up System

本地网页 MVP：肺结节多期 CT 时序特征提取、风险评估与个性化随访辅助决策系统。

## 当前版本定位

第一版用于演示和继续开发：

- 病例管理与临床工作台
- 多期 CT 随访时间轴
- 肺结节直径、体积、密度、实性成分等动态指标展示
- 三维配准、时序特征、ConvLSTM 推理的可替换算法接口
- AI 风险分层与个体化随访建议
- 结构化随访报告生成
- 数据集规范页面，展示真实 DICOM 多期目录、CSV 字段、标签枚举和质控规则
- 研究导出：基础队列表、测量表、分析研究表 CSV
- 模型接入状态页，检查 `.pt` / `.onnx` 权重、推理依赖、当前真实/代理模型模式，并支持模型输入 schema 与 dry-run 推理自检

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
4. 点击“运行时序分析”。
5. 查看 AI 风险评分、个性化随访建议和结构化报告。

## 真实数据与模型接入准备

- 数据集规范：前端侧边栏“数据集规范”页面读取 `GET /imports/spec`，展示 DICOM 目录、CSV 文件、标签枚举和质控规则。
- CSV 导入校验：在“影像上传”页上传 `patients.csv`、`studies.csv`、`nodules.csv`、`measurements.csv`，系统只做规范校验并返回报告，不写入数据库。
- CSV 导出：总览页和病例详情页可下载 `cohort-table.csv`、`measurements.csv`、`research-table.csv`；其中 `cohort-table.csv` 不依赖 AI 分析结果。
- 研究数据包：总览页和病例详情页可下载 `research-package.zip`，内含三张 CSV、`imports-spec.json`、`model-status.json` 和 `metadata.json`。
- 模型 artifact：将 TorchScript `temporal_model.pt` 或 ONNX `temporal_model.onnx` 放入 `backend/model_artifacts/`；TorchScript 需要安装 `torch`，ONNX 需要安装 `onnxruntime`。
- 模型状态：前端侧边栏“模型状态”页面读取 `GET /model/status`，显示权重文件、`torch` / `onnxruntime` 依赖和当前推理模式。
- 模型自检：模型状态页可调用 `POST /model/self-check`，使用内置三期 synthetic temporal fixture 校验 `temporal-nodule-v1` 输入 schema，并执行真实模型或代理 fallback dry-run。

## 后续扩展

- DICOM/NIfTI 真实读取：替换 `pipeline/preprocess.py`
- 结节分割与影像组学：扩展 `pipeline/features.py`
- ConvLSTM 模型训练与推理：替换 `pipeline/model.py`
- PDF/Word 报告导出：扩展 `routes/reports.py`
