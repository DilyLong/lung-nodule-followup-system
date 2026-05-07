import { AlertTriangle, ArrowLeft, BrainCircuit, CheckCircle, PlayCircle, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { fetchModelRuntimeStatus, runModelSelfCheck, type ModelRuntimeStatus, type ModelSelfCheckReport } from '../lib/api';

interface Props {
  setPage: (page: Page) => void;
}

function activeModeText(mode: string) {
  const labels: Record<string, string> = {
    real_torch_ready: '真实 PyTorch 模型就绪',
    real_onnx_ready: '真实 ONNX 模型就绪',
    surrogate_no_weights: '未检测到真实权重，使用代理模型',
    fallback_missing_dependency: '检测到权重但缺少推理依赖，使用代理模型',
  };
  return labels[mode] ?? mode;
}

function modelStatusText(status?: string) {
  const labels: Record<string, string> = {
    real_torch_loaded: '真实 PyTorch 模型 dry-run 通过',
    real_onnx_loaded: '真实 ONNX 模型 dry-run 通过',
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
  };
  return labels[name] ?? name;
}

function previewValue(value: unknown) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === 'boolean') return value ? '是' : '否';
  return String(value);
}

function inputSourceText(source: string) {
  const labels: Record<string, string> = {
    synthetic_temporal_fixture: '内置三期 synthetic temporal fixture',
  };
  return labels[source] ?? source;
}

export default function ModelStatusPage({ setPage }: Props) {
  const [status, setStatus] = useState<ModelRuntimeStatus | null>(null);
  const [selfCheck, setSelfCheck] = useState<ModelSelfCheckReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');
  const [checkError, setCheckError] = useState('');

  useEffect(() => {
    fetchModelRuntimeStatus()
      .then(setStatus)
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

  if (loading) {
    return <div className="page"><p className="empty">正在读取模型接入状态...</p></div>;
  }

  if (error || !status) {
    return <div className="page"><p className="empty">{error || '暂无模型状态。'}</p></div>;
  }

  const realReady = status.active_mode.startsWith('real_');

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
          <span>代理模型版本</span>
          <strong>{status.surrogate_model_version}</strong>
          <p>{status.fallback_model.name}</p>
        </div>
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
