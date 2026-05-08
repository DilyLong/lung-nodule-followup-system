import { AlertTriangle, ArrowLeft, BrainCircuit, CheckCircle, PlayCircle, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { fetchModelRuntimeStatus, fetchModelTrainingReadiness, loadDemoTrainingCohort, runModelSelfCheck, runModelTraining, type DemoTrainingCohortResult, type ModelRuntimeStatus, type ModelSelfCheckReport, type ModelTrainingReadiness, type ModelTrainingReport } from '../lib/api';

interface Props {
  setPage: (page: Page) => void;
}

function activeModeText(mode: string) {
  const labels: Record<string, string> = {
    real_torch_ready: '真实 PyTorch 模型就绪',
    real_onnx_ready: '真实 ONNX 模型就绪',
    real_json_ready: '队列训练 JSON 模型就绪',
    surrogate_no_weights: '未检测到真实权重，使用代理模型',
    fallback_missing_dependency: '检测到权重但缺少推理依赖，使用代理模型',
  };
  return labels[mode] ?? mode;
}

function modelStatusText(status?: string) {
  const labels: Record<string, string> = {
    real_torch_loaded: '真实 PyTorch 模型 dry-run 通过',
    real_onnx_loaded: '真实 ONNX 模型 dry-run 通过',
    real_json_loaded: '队列训练 JSON 模型 dry-run 通过',
    surrogate_no_weights: '代理模型 dry-run 通过',
    fallback_missing_dependency: '缺少推理依赖，已回退代理模型',
    fallback_load_error: '真实模型加载失败，已回退代理模型',
    fallback_schema_mismatch: '真实模型输入契约不匹配，已回退代理模型',
    fallback_inference_error: '真实模型推理失败，已回退代理模型',
  };
  return status ? labels[status] ?? status : '未运行';
}

function statusText(status: string) {
  const labels: Record<string, string> = {
    ready: '就绪',
    missing: '未检测到',
    missing_dependency: '缺少依赖',
  };
  return labels[status] ?? status;
}

function checkNameText(name: string) {
  const labels: Record<string, string> = {
    artifact_status: '权重与依赖状态',
    input_schema: '输入 Schema 校验',
    inference: '推理 dry-run',
    output_contract: '输出契约校验',
  };
  return labels[name] ?? name;
}

function previewValue(value: unknown) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function inputSourceText(source: string) {
  const labels: Record<string, string> = {
    synthetic_temporal_fixture: '内置三期 synthetic temporal fixture',
  };
  return labels[source] ?? source;
}

function metricLabel(key: string) {
  const labels: Record<string, string> = {
    auc: 'AUC',
    accuracy: 'Accuracy',
    sensitivity: 'Sensitivity',
    specificity: 'Specificity',
    brier_score: 'Brier Score',
  };
  return labels[key] ?? key;
}

function labelText(value: unknown) {
  if (value === 1) return '阳性/恶性';
  if (value === 0) return '阴性/良性';
  return previewValue(value);
}

export default function ModelStatusPage({ setPage }: Props) {
  const [status, setStatus] = useState<ModelRuntimeStatus | null>(null);
  const [selfCheck, setSelfCheck] = useState<ModelSelfCheckReport | null>(null);
  const [trainingReadiness, setTrainingReadiness] = useState<ModelTrainingReadiness | null>(null);
  const [trainingReport, setTrainingReport] = useState<ModelTrainingReport | null>(null);
  const [operator, setOperator] = useState('系统');
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [training, setTraining] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoResult, setDemoResult] = useState<DemoTrainingCohortResult | null>(null);
  const [error, setError] = useState('');
  const [checkError, setCheckError] = useState('');
  const [trainingError, setTrainingError] = useState('');

  useEffect(() => {
    Promise.all([fetchModelRuntimeStatus(), fetchModelTrainingReadiness()])
      .then(([runtimeStatus, readiness]) => {
        setStatus(runtimeStatus);
        setTrainingReadiness(readiness);
      })
      .catch(() => setError('无法读取模型状态，请确认后端服务已启动。'))
      .finally(() => setLoading(false));
  }, []);

  async function handleSelfCheck() {
    setChecking(true);
    setCheckError('');
    try {
      const report = await runModelSelfCheck();
      setSelfCheck(report);
      setStatus(report.runtime_status);
    } catch {
      setCheckError('模型自检失败，请确认后端服务已启动并查看后端日志。');
    } finally {
      setChecking(false);
    }
  }

  async function handleLoadDemoCohort() {
    setDemoLoading(true);
    setTrainingError('');
    try {
      const result = await loadDemoTrainingCohort();
      const readiness = await fetchModelTrainingReadiness();
      setDemoResult(result);
      setTrainingReadiness(readiness);
    } catch {
      setTrainingError('加载 synthetic demo cohort 失败，请确认后端服务已启动。');
    } finally {
      setDemoLoading(false);
    }
  }

  async function handleTraining() {
    setTraining(true);
    setTrainingError('');
    try {
      const report = await runModelTraining(operator.trim() || '系统');
      const [runtimeStatus, readiness] = await Promise.all([fetchModelRuntimeStatus(), fetchModelTrainingReadiness()]);
      setTrainingReport(report);
      setStatus(runtimeStatus);
      setTrainingReadiness(readiness);
    } catch {
      setTrainingError('模型训练请求失败，请确认后端服务已启动并查看后端日志。');
    } finally {
      setTraining(false);
    }
  }

  if (loading) {
    return <div className="page"><p className="empty">正在读取模型接入状态...</p></div>;
  }

  if (error || !status) {
    return <div className="page"><p className="empty">{error || '暂无模型状态。'}</p></div>;
  }

  const realReady = status.active_mode.startsWith('real_');
  const latestTrainingReport = trainingReport ?? trainingReadiness?.latest_report as ModelTrainingReport | null;
  const trainingMetrics = latestTrainingReport?.metrics ?? null;
  const calibrationBins = latestTrainingReport?.calibration_bins ?? [];
  const trainingSamples = latestTrainingReport?.samples ?? [];

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Model integration</p>
          <h1>模型接入状态</h1>
          <span>检查真实权重文件、推理依赖和当前实际推理模式，并可运行输入契约与推理 dry-run 自检。</span>
        </div>
        <div className="button-row">
          <button className="primary" onClick={handleSelfCheck} disabled={checking}><PlayCircle size={17} /> {checking ? '自检中...' : '运行模型自检'}</button>
          <button className="ghost" onClick={() => setPage({ name: 'dashboard' })}><ArrowLeft size={17} /> 返回工作台</button>
        </div>
      </header>

      <section className="metric-row">
        <div className={`metric-card ${realReady ? '' : 'accent'}`}>
          <span>当前模式</span>
          <strong>{activeModeText(status.active_mode)}</strong>
          <p>后端：{status.active_backend}</p>
        </div>
        <div className="metric-card">
          <span>输入 Schema</span>
          <strong>{status.input_schema_version}</strong>
          <p>真实模型需保持该输入契约。</p>
        </div>
        <div className="metric-card">
          <span>队列训练样本</span>
          <strong>{trainingReadiness?.eligible_sample_count ?? '—'}</strong>
          <p>阳性 {trainingReadiness?.positive_count ?? '—'} / 阴性 {trainingReadiness?.negative_count ?? '—'}</p>
        </div>
      </section>

      <section className="panel spec-section">
        <h2><BrainCircuit size={19} /> 队列训练与校准</h2>
        <p className="model-note">基于导入结节的临床/病理标签和多期测量训练本地 JSON 风险模型，用于进入真实数据训练闭环。</p>
        <div className="training-toolbar">
          <label>
            操作者
            <input value={operator} onChange={(event) => setOperator(event.target.value)} placeholder="请输入操作者" />
          </label>
          <button className="ghost" onClick={handleLoadDemoCohort} disabled={demoLoading}>
            <PlayCircle size={17} /> {demoLoading ? '加载中...' : '加载示例训练队列'}
          </button>
          <button className="primary" onClick={handleTraining} disabled={training || !trainingReadiness?.ready}>
            <PlayCircle size={17} /> {training ? '训练中...' : '运行队列训练'}
          </button>
        </div>
        <div className="info-banner"><AlertTriangle size={17} /> 队列训练页仅用于科研建模闭环和产品演示；当前 JSON 模型不是获批医疗器械模型，不能直接用于临床诊疗决策。</div>
        <div className="model-summary">
          <div><span>训练就绪</span><strong>{trainingReadiness?.ready ? '是' : '否'}</strong></div>
          <div><span>可用样本</span><strong>{trainingReadiness?.eligible_sample_count ?? '—'}</strong></div>
          <div><span>阳性 / 阴性</span><strong>{trainingReadiness ? `${trainingReadiness.positive_count} / ${trainingReadiness.negative_count}` : '—'}</strong></div>
          <div><span>排除结节</span><strong>{trainingReadiness?.excluded_count ?? '—'}</strong></div>
          <div><span>JSON Artifact</span><strong>{trainingReadiness?.artifact_exists ? '已生成' : '未生成'}</strong></div>
          <div><span>训练报告</span><strong>{trainingReadiness?.training_report_exists ? '已生成' : '未生成'}</strong></div>
        </div>
        {demoResult && <div className="success-banner"><CheckCircle size={17} /> 已加载 synthetic demo cohort：{demoResult.case_count} 个病例，当前 {demoResult.after.nodule_count} 个结节 / {demoResult.after.measurement_count} 条测量，可直接运行训练演示。</div>}
        {trainingError && <div className="info-banner"><AlertTriangle size={17} /> {trainingError}</div>}
        {!trainingReadiness?.ready && <div className="info-banner"><AlertTriangle size={17} /> 至少需要 4 个带标签结节，且同时包含良性和恶性样本。请在 CSV 中补充 clinical_label / pathology_label 和多期测量后再训练。</div>}
        {trainingReport && (
          <div className={trainingReport.trained ? 'success-banner' : 'info-banner'}>
            {trainingReport.trained ? <CheckCircle size={17} /> : <AlertTriangle size={17} />}
            {trainingReport.message}
          </div>
        )}
        {trainingMetrics && (
          <section className="training-insight-panel">
            <h3>训练结果解释</h3>
            <div className="model-summary">
              {Object.entries(trainingMetrics).map(([key, value]) => (
                <div key={key}><span>{metricLabel(key)}</span><strong>{value.toFixed(3)}</strong></div>
              ))}
            </div>
            <p className="model-note">AUC/Accuracy/Sensitivity/Specificity 基于当前队列的验证切分；Brier Score 越低代表概率校准越好。Synthetic demo 样本量较小，仅用于展示训练闭环。</p>
          </section>
        )}
        {calibrationBins.length > 0 && (
          <section className="training-insight-panel">
            <h3>校准分箱</h3>
            <div className="table-card validation-table">
              <table>
                <thead><tr><th>预测区间</th><th>样本数</th><th>平均预测概率</th><th>观察阳性率</th></tr></thead>
                <tbody>
                  {calibrationBins.map((bin, index) => (
                    <tr key={index}>
                      <td>{previewValue(bin.range)}</td>
                      <td>{previewValue(bin.count)}</td>
                      <td>{previewValue(bin.mean_predicted)}</td>
                      <td>{previewValue(bin.observed_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
        {trainingSamples.length > 0 && (
          <section className="training-insight-panel">
            <h3>训练样本列表</h3>
            <div className="status-grid">
              <div className="status-card"><span>训练样本</span><strong>{latestTrainingReport?.train_sample_count ?? '—'}</strong></div>
              <div className="status-card"><span>验证样本</span><strong>{latestTrainingReport?.validation_sample_count ?? '—'}</strong></div>
              <div className="status-card"><span>阳性样本</span><strong>{latestTrainingReport?.positive_count ?? trainingReadiness?.positive_count ?? '—'}</strong></div>
              <div className="status-card"><span>阴性样本</span><strong>{latestTrainingReport?.negative_count ?? trainingReadiness?.negative_count ?? '—'}</strong></div>
            </div>
            <div className="table-card validation-table">
              <table>
                <thead><tr><th>患者</th><th>结节</th><th>标签</th><th>标签来源</th></tr></thead>
                <tbody>
                  {trainingSamples.slice(0, 16).map((sample, index) => (
                    <tr key={`${sample.patient_code}-${sample.nodule_id}-${index}`}>
                      <td>{previewValue(sample.patient_code)}</td>
                      <td>{previewValue(sample.nodule_label)} #{previewValue(sample.nodule_id)}</td>
                      <td>{labelText(sample.label)}</td>
                      <td>{previewValue(sample.label_source)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
        {(trainingReadiness?.latest_report || trainingReport) && (
          <div className="spec-kv-grid">
            <div><span>模型版本</span><strong>{previewValue(trainingReport?.model_version ?? trainingReadiness?.latest_report?.model_version)}</strong></div>
            <div><span>Artifact 路径</span><strong>{trainingReport?.artifact_path ?? trainingReadiness?.artifact_path}</strong></div>
            <div><span>训练报告路径</span><strong>{trainingReport?.training_report_path ?? trainingReadiness?.training_report_path}</strong></div>
          </div>
        )}
        {(trainingReadiness?.exclusions.length ?? 0) > 0 && (
          <div className="table-card validation-table">
            <table>
              <thead>
                <tr><th>结节 ID</th><th>患者 ID</th><th>排除原因</th></tr>
              </thead>
              <tbody>
                {trainingReadiness?.exclusions.slice(0, 8).map((item, index) => (
                  <tr key={index}>
                    <td>{previewValue(item.nodule_id)}</td>
                    <td>{previewValue(item.patient_id)}</td>
                    <td>{previewValue(item.reason)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className="panel spec-section">
        <h2><BrainCircuit size={19} /> 权重文件</h2>
        <p className="model-note">目录：{status.artifact_dir}</p>
        <div className="table-card spec-table-card">
          <table>
            <thead>
              <tr>
                <th>文件</th>
                <th>格式</th>
                <th>文件状态</th>
                <th>依赖</th>
                <th>依赖状态</th>
                <th>Hash</th>
              </tr>
            </thead>
            <tbody>
              {status.artifacts.map((artifact) => (
                <tr key={artifact.name}>
                  <td><strong>{artifact.name}</strong><br /><span>{artifact.path}</span></td>
                  <td>{artifact.format}</td>
                  <td><span className={`model-status-chip ${artifact.exists ? artifact.status === 'missing_dependency' ? 'fallback' : 'real' : 'proxy'}`}>{statusText(artifact.status)}</span></td>
                  <td>{artifact.dependency}</td>
                  <td>{artifact.dependency_available ? <span className="dependency-ok"><CheckCircle size={15} /> 可用</span> : <span className="dependency-missing"><XCircle size={15} /> 不可用</span>}</td>
                  <td>{artifact.sha256 ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel spec-section">
          <h2>推理依赖</h2>
          <div className="spec-enum-list">
            {Object.entries(status.dependencies).map(([name, available]) => (
              <div key={name}>
                <strong>{name}</strong>
                <span className={`model-status-chip ${available ? 'real' : 'fallback'}`}>{available ? '已安装' : '未安装'}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="panel spec-section">
          <h2>Fallback 模型</h2>
          <div className="spec-kv-grid">
            <div><span>名称</span><strong>{status.fallback_model.name}</strong></div>
            <div><span>后端</span><strong>{status.fallback_model.backend}</strong></div>
            <div><span>状态</span><strong>{status.fallback_model.status}</strong></div>
          </div>
        </div>
      </section>

      {checkError && <div className="info-banner"><AlertTriangle size={17} /> {checkError}</div>}

      {selfCheck && (
        <section className="panel spec-section self-check-panel">
          <h2><PlayCircle size={19} /> 模型接入自检报告</h2>
          <div className={selfCheck.passed ? 'success-banner' : 'info-banner'}>
            {selfCheck.passed ? <CheckCircle size={17} /> : <AlertTriangle size={17} />}
            {selfCheck.passed ? '自检通过：模型输入契约与 dry-run 推理均可执行。' : '自检未完全通过：请查看 checks 与 issues。'}
          </div>

          <div className="spec-kv-grid">
            <div><span>运行模式</span><strong>{activeModeText(selfCheck.mode)}</strong></div>
            <div><span>后端</span><strong>{selfCheck.backend}</strong></div>
            <div><span>Demo 输入</span><strong>{inputSourceText(selfCheck.demo_input_source)}</strong></div>
          </div>

          <div className="table-card validation-table">
            <table>
              <thead>
                <tr>
                  <th>检查项</th>
                  <th>结果</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                {selfCheck.checks.map((check) => (
                  <tr key={check.name}>
                    <td>{checkNameText(check.name)}</td>
                    <td><span className={`model-status-chip ${check.passed ? 'real' : 'fallback'}`}>{check.passed ? '通过' : '未通过'}</span></td>
                    <td>{check.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selfCheck.issues.length > 0 && (
            <div className="table-card validation-table">
              <table>
                <thead>
                  <tr>
                    <th>级别</th>
                    <th>字段</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {selfCheck.issues.map((issue, index) => (
                    <tr key={`${issue.field}-${index}`}>
                      <td><span className={`severity-badge ${issue.severity}`}>{issue.severity}</span></td>
                      <td>{issue.field}</td>
                      <td>{issue.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {selfCheck.inference && (
            <div className="model-summary">
              <div><span>风险评分</span><strong>{selfCheck.inference.risk_score ?? '—'}</strong></div>
              <div><span>风险分层</span><strong>{selfCheck.inference.risk_level ?? '—'}</strong></div>
              <div><span>推理状态</span><strong>{modelStatusText(selfCheck.inference.model_status)}</strong></div>
              <div><span>输入特征</span><strong>{selfCheck.inference.model_input_feature_count ?? '—'}</strong></div>
              <div><span>Artifact Hash</span><strong>{selfCheck.inference.model_artifact_hash ?? '—'}</strong></div>
              <div><span>推理时间</span><strong>{selfCheck.inference.inference_started_at ? new Date(selfCheck.inference.inference_started_at).toLocaleString() : '—'}</strong></div>
            </div>
          )}

          {selfCheck.inference?.fallback_reason && <div className="info-banner">Fallback 原因：{selfCheck.inference.fallback_reason}</div>}

          <div className="detail-grid">
            <div className="panel spec-section">
              <h2>模型输入预览</h2>
              <div className="spec-kv-grid">
                <div><span>Schema</span><strong>{previewValue(selfCheck.model_input_preview.input_schema_version)}</strong></div>
                <div><span>时间点数量</span><strong>{previewValue(selfCheck.model_input_preview.timepoint_count)}</strong></div>
              </div>
              <div className="table-card validation-table">
                <table>
                  <thead>
                    <tr>
                      <th>study_id</th>
                      <th>study_date</th>
                      <th>diameter_mm</th>
                      <th>volume_mm3</th>
                      <th>mean_hu</th>
                      <th>solid%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(selfCheck.model_input_preview.time_series ?? []).map((point, index) => (
                      <tr key={index}>
                        <td>{previewValue(point.study_id)}</td>
                        <td>{previewValue(point.study_date)}</td>
                        <td>{previewValue(point.diameter_mm)}</td>
                        <td>{previewValue(point.volume_mm3)}</td>
                        <td>{previewValue(point.mean_hu)}</td>
                        <td>{previewValue(point.solid_component_percent)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="panel spec-section">
              <h2>临床与衍生特征</h2>
              <div className="spec-enum-list">
                {Object.entries(selfCheck.model_input_preview.clinical_features ?? {}).map(([key, value]) => (
                  <div key={key}><strong>{key}</strong><span>{previewValue(value)}</span></div>
                ))}
                {Object.entries(selfCheck.model_input_preview.derived_features ?? {}).slice(0, 8).map(([key, value]) => (
                  <div key={key}><strong>{key}</strong><span>{previewValue(value)}</span></div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {!realReady && (
        <div className="info-banner">当前未使用真实模型权重。将 TorchScript `temporal_model.pt` 或 ONNX `temporal_model.onnx` 放入模型目录，并安装对应依赖后，系统会优先尝试真实模型推理。</div>
      )}
    </div>
  );
}
