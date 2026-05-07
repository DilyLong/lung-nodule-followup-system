# Changelog

## 2026-05-07

### Added

- 新增“数据集规范 / 真实数据准备”前端页面，展示 `/imports/spec` 的 DICOM 目录组织、CSV 字段、标签枚举和质控规则，便于整理真实多期 CT 与标注数据。
- 新增 `cohort-table.csv` 基础队列表导出，无需运行 AI 分析也可导出患者、结节、多期检查与核心测量指标，并在总览页和病例详情页提供下载入口。
- 新增模型接入状态接口与前端页面，显示 `temporal_model.pt` / `temporal_model.onnx` 权重文件、`torch` / `onnxruntime` 依赖可用性、当前真实模型或代理模型运行模式。
- 新增 CSV 数据集导入前校验功能，可上传 `patients.csv`、`studies.csv`、`nodules.csv`、`measurements.csv`，在不写入数据库的前提下检查必填字段、枚举、日期、数值和跨表关联，并在前端展示校验报告。
