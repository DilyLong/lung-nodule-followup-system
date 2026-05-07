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
  model_input?: {
    timepoint_count?: number;
    clinical_features?: Record<string, unknown>;
  };
  contributions?: Contribution[];
}

function parseRisk(analysis?: Analysis): ModelRiskPayload | null {
  if (!analysis) return null;
  try {
    const features = JSON.parse(analysis.features_json);
    return features.risk ?? null;
  } catch {
    return null;
  }
}

function statusText(status?: string) {
  if (status === 'surrogate_no_weights') return 'ConvLSTM 兼容代理模型';
  return status ?? '未记录';
}

export default function ModelExplanationPanel({ analysis }: Props) {
  const risk = parseRisk(analysis);

  if (!analysis) {
    return <p className="empty compact">运行时序分析后显示模型输入、推理后端和风险贡献因子。</p>;
  }

  if (!risk) {
    return <p className="empty compact">该次分析没有模型解释详情，请重新运行时序分析。</p>;
  }

  const contributions = risk.contributions?.slice(0, 5) ?? [];
  const maxPoints = Math.max(...contributions.map((item) => item.points), 0.01);

  return (
    <div className="model-explanation">
      <div className="model-summary">
        <div><span>模型状态</span><strong>{statusText(risk.model_status)}</strong></div>
        <div><span>模型版本</span><strong>{risk.model_version ?? '-'}</strong></div>
        <div><span>输入时间点</span><strong>{risk.model_input?.timepoint_count ?? '-'}</strong></div>
      </div>
      <p className="model-note">
        {risk.model_name ?? 'Temporal model'} · 后端 {risk.backend ?? '-'} · 输入 schema {risk.input_schema_version ?? '-'}
      </p>
      {risk.model_status === 'surrogate_no_weights' && (
        <p className="info-banner compact">当前为可解释代理模型，接口已兼容后续 PyTorch ConvLSTM 权重接入。</p>
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
