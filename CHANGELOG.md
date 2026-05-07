# Changelog

## 2026-05-07

### Added

- 新增“数据集规范 / 真实数据准备”前端页面，展示 `/imports/spec` 的 DICOM 目录组织、CSV 字段、标签枚举和质控规则，便于整理真实多期 CT 与标注数据。
- 新增 `cohort-table.csv` 基础队列表导出，无需运行 AI 分析也可导出患者、结节、多期检查与核心测量指标，并在总览页和病例详情页提供下载入口。
- 新增模型接入状态接口与前端页面，显示 `temporal_model.pt` / `temporal_model.onnx` 权重文件、`torch` / `onnxruntime` 依赖可用性、当前真实模型或代理模型运行模式。
- 新增 CSV 数据集导入前校验功能，可上传 `patients.csv`、`studies.csv`、`nodules.csv`、`measurements.csv`，在不写入数据库的前提下检查必填字段、枚举、日期、数值和跨表关联，并在前端展示校验报告。
- 新增研究数据包 ZIP 一键导出，打包基础队列表、测量表、分析研究表、数据集规范、模型状态和 metadata，支持全队列与单病例导出。
- 新增模型接入自检 / dry-run 功能，使用内置三期 synthetic temporal fixture 校验输入 schema，并验证真实模型或代理 fallback 推理链路。
- 新增多结节独立时序分析能力，病例详情页可选择目标结节运行风险评分，分析结果记录 `nodule_id`，研究导出按结节维度关联最新风险。
- 新增医生可编辑确认版报告，支持报告正文 Markdown、医生意见和随访建议编辑，可保存草稿并确认最终版。
- 新增风险评分版本追踪，每次分析记录数据 schema、特征版本、模型 artifact/hash、推理时间和输入特征维度，并同步到研究表导出。
