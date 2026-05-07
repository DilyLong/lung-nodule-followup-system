import { ArrowLeft, BrainCircuit, CheckCircle, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { fetchModelRuntimeStatus, type ModelRuntimeStatus } from '../lib/api';

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

function statusText(status: string) {
  const labels: Record<string, string> = {
    ready: '就绪',
    missing: '未检测到',
    missing_dependency: '缺少依赖',
  };
  return labels[status] ?? status;
}

export default function ModelStatusPage({ setPage }: Props) {
  const [status, setStatus] = useState<ModelRuntimeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchModelRuntimeStatus()
      .then(setStatus)
      .catch(() => setError('无法读取模型状态，请确认后端服务已启动。'))
      .finally(() => setLoading(false));
  }, []);

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
          <span>检查真实权重文件、推理依赖和当前实际推理模式，确认系统使用真实模型还是代理模型。</span>
        </div>
        <button className="ghost" onClick={() => setPage({ name: 'dashboard' })}><ArrowLeft size={17} /> 返回工作台</button>
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
                  <td><span className={`model-status-chip ${artifact.exists ? 'real' : 'proxy'}`}>{statusText(artifact.status)}</span></td>
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

      {!realReady && (
        <div className="info-banner">当前未使用真实模型权重。将 TorchScript `temporal_model.pt` 或 ONNX `temporal_model.onnx` 放入模型目录，并安装对应依赖后，系统会优先尝试真实模型推理。</div>
      )}
    </div>
  );
}
