import type { Analysis } from '../lib/api';

interface Props {
  analysis?: Analysis;
}

interface Contribution {
  key: string;
  label: string;
  value: string;
  weight: number;
  points: number;
}

interface ModelRiskPayload {
  model_name?: string;
  model_status?: string;
  model_version?: string;
  input_schema_version?: string;
  backend?: string;
  fallback_reason?: string;
  model_artifact?: string;
  model_artifact_hash?: string;
  model_input_feature_count?: number;
  inference_started_at?: string;
  data_schema_version?: string;
  feature_version?: string;
  model_input?: {
    timepoint_count?: number;
    clinical_features?: Record<string, unknown>;
  };
  contributions?: Contribution[];
}

interface RiskTracePayload {
  data_schema_version?: string;
  feature_version?: string;
  input_schema_version?: string;
  model_version?: string;
  model_artifact?: string;
  model_artifact_hash?: string;
  backend?: string;
  model_status?: string;
  inference_started_at?: string;
  analysis_generated_at?: string;
  model_input_feature_count?: number;
}

function parsePayload(analysis?: Analysis): { risk: ModelRiskPayload | null; trace: RiskTracePayload } {
  if (!analysis) return { risk: null, trace: {} };
  try {
    const features = JSON.parse(analysis.features_json);
    return { risk: features.risk ?? null, trace: features.trace ?? {} };
  } catch {
    return { risk: null, trace: {} };
  }
}

function statusText(status?: string) {
  const labels: Record<string, string> = {
    real_torch_loaded: '真实 PyTorch 模型',
    real_onnx_loaded: '真实 ONNX 模型',
    surrogate_no_weights: 'ConvLSTM 兼容代理模型',
    fallback_missing_artifact: '缺少权重，已回退代理模型',
    fallback_missing_dependency: '缺少推理依赖，已回退代理模型',
    fallback_load_error: '模型加载失败，已回退代理模型',
    fallback_inference_error: '模型推理失败，已回退代理模型',
    fallback_schema_mismatch: '模型 schema 不匹配，已回退代理模型',
  };
  return status ? labels[status] ?? status : '未记录';
}

function modelMode(status?: string) {
  if (status?.startsWith('real_')) return 'real';
  if (status?.startsWith('fallback_')) return 'fallback';
  return 'proxy';
}

function formatDateTime(value?: string) {
  return value ? new Date(value).toLocaleString() : '-';
}

export default function ModelExplanationPanel({ analysis }: Props) {
  const { risk, trace } = parsePayload(analysis);

  if (!analysis) {
    return <p className="empty compact">运行时序分析后显示模型输入、推理后端和风险贡献因子。</p>;
  }

  if (!risk) {
    return <p className="empty compact">该次分析没有模型解释详情，请重新运行时序分析。</p>;
  }

  const contributions = risk.contributions?.slice(0, 5) ?? [];
  const maxPoints = Math.max(...contributions.map((item) => item.points), 0.01);
  const mode = modelMode(risk.model_status);
  const artifactName = trace.model_artifact ?? risk.model_artifact;
  const artifactHash = trace.model_artifact_hash ?? risk.model_artifact_hash;

  return (
    <div className="model-explanation">
      <div className="model-summary">
        <div><span>模型状态</span><strong>{statusText(risk.model_status)}</strong></div>
        <div><span>模型版本</span><strong>{trace.model_version ?? risk.model_version ?? '-'}</strong></div>
        <div><span>输入时间点</span><strong>{risk.model_input?.timepoint_count ?? '-'}</strong></div>
      </div>
      <p className="model-note">
        {risk.model_name ?? 'Temporal model'} · 后端 {trace.backend ?? risk.backend ?? '-'} · 输入 schema {trace.input_schema_version ?? risk.input_schema_version ?? '-'}
        {artifactName ? ` · 权重 ${artifactName}` : ''}
      </p>
      <div className="model-summary">
        <div><span>数据 Schema</span><strong>{trace.data_schema_version ?? risk.data_schema_version ?? '-'}</strong></div>
        <div><span>特征版本</span><strong>{trace.feature_version ?? risk.feature_version ?? '-'}</strong></div>
        <div><span>输入特征维度</span><strong>{trace.model_input_feature_count ?? risk.model_input_feature_count ?? '-'}</strong></div>
      </div>
      <p className="model-note">
        推理时间 {formatDateTime(trace.inference_started_at ?? risk.inference_started_at)}
        {trace.analysis_generated_at ? ` · 分析生成 ${formatDateTime(trace.analysis_generated_at)}` : ''}
        {artifactHash ? ` · artifact hash ${artifactHash}` : ''}
      </p>
      {mode === 'real' && (
        <p className="success-banner compact">当前分析已使用真实模型权重推理，风险评分来自模型 artifact。</p>
      )}
      {mode === 'proxy' && (
        <p className="info-banner compact">当前为可解释代理模型，接口已兼容后续 PyTorch / ONNX 权重接入。</p>
      )}
      {mode === 'fallback' && (
        <p className="info-banner compact">真实模型未完成推理，系统已安全回退到代理模型。{risk.fallback_reason ? `原因：${risk.fallback_reason}` : ''}</p>
      )}
      <div className="contribution-list">
        {contributions.map((item) => (
          <div className="contribution-item" key={item.key}>
            <div>
              <strong>{item.label}</strong>
              <span>{item.value} · 权重 {item.weight}</span>
            </div>
            <div className="contribution-bar">
              <span style={{ width: `${Math.max(4, (item.points / maxPoints) * 100)}%` }} />
            </div>
            <b>{item.points.toFixed(3)}</b>
          </div>
        ))}
        {contributions.length === 0 && <span>暂无贡献因子。</span>}
      </div>
    </div>
  );
}
