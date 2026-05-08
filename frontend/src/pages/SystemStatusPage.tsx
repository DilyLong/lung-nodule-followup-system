import { ArrowLeft, CheckCircle, Clock, Database, Download, Server, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { fetchSystemStatus, type SystemStatus } from '../lib/api';

interface Props {
  setPage: (page: Page) => void;
}

function modeText(mode: string) {
  const labels: Record<string, string> = {
    real_torch_ready: '真实 PyTorch 模型就绪',
    real_onnx_ready: '真实 ONNX 模型就绪',
    real_json_ready: '队列训练 JSON 模型就绪',
    surrogate_no_weights: '代理模型运行',
    fallback_missing_dependency: '权重存在但依赖缺失',
  };
  return labels[mode] ?? mode;
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '暂无';
}

function targetPage(page: string): Page {
  if (page === 'upload') return { name: 'upload' };
  if (page === 'modelStatus') return { name: 'modelStatus' };
  return { name: 'dashboard' };
}

export default function SystemStatusPage({ setPage }: Props) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSystemStatus()
      .then(setStatus)
      .catch(() => setError('无法读取系统状态，请确认后端服务已启动。'));
  }, []);

  if (error) {
    return <div className="page"><p className="empty">{error}</p></div>;
  }

  if (!status) {
    return <div className="page"><p className="empty">正在加载系统状态总览...</p></div>;
  }

  const databaseItems = [
    ['病例', status.database.patient_count],
    ['检查', status.database.study_count],
    ['结节', status.database.nodule_count],
    ['测量', status.database.measurement_count],
    ['分析', status.database.analysis_count],
    ['报告', status.database.report_count],
    ['最终版报告', status.database.final_report_count],
    ['导入批次', status.database.import_batch_count],
  ];

  const measurementSources = status.database.measurement_sources ?? {};
  const dataQuality = status.data_quality;
  const trainingReadiness = dataQuality?.training_readiness;
  const followupInterval = dataQuality?.followup_interval_days;
  const labelDistribution = dataQuality?.label_distribution ?? {};
  const missingFields = dataQuality?.missing_fields ?? {};
  const actions = status.actions ?? [];

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">System overview</p>
          <h1>系统状态总览</h1>
          <span>集中查看后端健康、数据规模、模型接入、研究导出和功能成熟度。</span>
        </div>
        <button className="ghost" onClick={() => setPage({ name: 'dashboard' })}><ArrowLeft size={17} /> 返回工作台</button>
      </header>

      <section className="metric-row">
        <div className="metric-card accent">
          <span>后端状态</span>
          <strong>{status.backend.status.toUpperCase()}</strong>
          <p>API {status.backend.api_version} · {formatDate(status.backend.checked_at)}</p>
        </div>
        <div className="metric-card">
          <span>病例 / 结节</span>
          <strong>{status.database.patient_count} / {status.database.nodule_count}</strong>
          <p>检查 {status.database.study_count}，测量 {status.database.measurement_count}</p>
        </div>
        <div className="metric-card">
          <span>模型模式</span>
          <strong>{modeText(status.model.active_mode)}</strong>
          <p>{status.model.active_backend} · {status.model.input_schema_version}</p>
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel spec-section">
          <h2><Database size={19} /> 数据库规模</h2>
          <div className="status-grid">
            {databaseItems.map(([label, value]) => (
              <div className="status-card" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="panel spec-section">
          <h2><Clock size={19} /> 最近活动</h2>
          <div className="spec-kv-grid">
            <div><span>最近分析</span><strong>{status.latest.analysis ? `${status.latest.analysis.risk_level} ${status.latest.analysis.risk_score.toFixed(2)}` : '暂无'}</strong><span>{formatDate(status.latest.analysis?.created_at)}</span></div>
            <div><span>最近报告</span><strong>{status.latest.report?.status ?? '暂无'}</strong><span>{formatDate(status.latest.report?.created_at)}</span></div>
            <div><span>最近导入批次</span><strong>{status.latest.import_batch ? `#${status.latest.import_batch.id} · ${status.latest.import_batch.status} · QC ${status.latest.import_batch.qc_score.toFixed(1)}` : '暂无'}</strong><span>{formatDate(status.latest.import_batch?.created_at)}</span></div>
            <div><span>最近最终版</span><strong>{status.latest.final_report?.status ?? '暂无'}</strong><span>{formatDate(status.latest.final_report?.finalized_at)}</span></div>
          </div>
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel spec-section">
          <h2><Server size={19} /> 模型接入</h2>
          <div className="table-card validation-table">
            <table>
              <thead>
                <tr>
                  <th>文件</th>
                  <th>状态</th>
                  <th>依赖</th>
                  <th>Hash</th>
                </tr>
              </thead>
              <tbody>
                {status.model.artifacts.map((artifact) => (
                  <tr key={artifact.name}>
                    <td>{artifact.name}</td>
                    <td><span className={`model-status-chip ${artifact.exists ? artifact.status === 'ready' ? 'real' : 'fallback' : 'proxy'}`}>{artifact.status}</span></td>
                    <td>{artifact.dependency} · {artifact.dependency_available ? '可用' : '不可用'}</td>
                    <td>{artifact.sha256 ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel spec-section">
          <h2><Clock size={19} /> 测量来源</h2>
          <div className="status-grid">
            {Object.entries(measurementSources).map(([source, count]) => (
              <div className="status-card" key={source}><span>{source}</span><strong>{count}</strong></div>
            ))}
          </div>
        </div>
        <div className="panel spec-section">
          <h2><Download size={19} /> 研究导出</h2>
          <div className="readiness-list">
            {status.exports.map((item) => (
              <div key={item.endpoint}>
                <span className={`status-dot ${item.available ? 'ok' : 'missing'}`} />
                <div><strong>{item.name}</strong><span>{item.endpoint}</span></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel spec-section">
          <h2><CheckCircle size={19} /> 数据质量看板</h2>
          <div className="status-grid">
            <div className="status-card"><span>可训练样本</span><strong>{trainingReadiness?.eligible_sample_count ?? '—'}</strong></div>
            <div className="status-card"><span>阳性 / 阴性</span><strong>{trainingReadiness ? `${trainingReadiness.positive_count} / ${trainingReadiness.negative_count}` : '—'}</strong></div>
            <div className="status-card"><span>排除样本</span><strong>{trainingReadiness?.excluded_count ?? '—'}</strong></div>
            <div className="status-card"><span>随访间隔中位数</span><strong>{followupInterval?.median ?? '—'} 天</strong></div>
          </div>
        </div>
        <div className="panel spec-section">
          <h2>标签分布</h2>
          <div className="status-grid">
            {Object.entries(labelDistribution).map(([label, count]) => (
              <div className="status-card" key={label}><span>{label}</span><strong>{count}</strong></div>
            ))}
          </div>
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel spec-section">
          <h2>缺失字段</h2>
          <div className="status-grid">
            {Object.entries(missingFields).map(([field, count]) => (
              <div className="status-card" key={field}><span>{field}</span><strong>{count}</strong></div>
            ))}
          </div>
        </div>
        <div className="panel spec-section">
          <h2>训练排除原因</h2>
          <div className="readiness-list">
            {(trainingReadiness?.top_exclusions ?? []).map((item, index) => (
              <div key={index}><span className="status-dot missing" /><div><strong>结节 {String(item.nodule_id ?? '-')}</strong><span>{String(item.reason ?? 'unknown')}</span></div></div>
            ))}
            {(trainingReadiness?.top_exclusions?.length ?? 0) === 0 && <div><span className="status-dot ok" /><div><strong>暂无排除样本</strong><span>当前训练队列字段完整或后端未返回训练质控字段。</span></div></div>}
          </div>
        </div>
      </section>

      <section className="panel spec-section">
        <h2>下一步行动建议</h2>
        <div className="action-grid">
          {actions.map((action) => (
            <div className={`action-card ${action.severity}`} key={action.key}>
              <strong>{action.title}</strong>
              <span>{action.description}</span>
              <button className="small-action" onClick={() => setPage(targetPage(action.target_page))}>去处理</button>
            </div>
          ))}
          {actions.length === 0 && <div className="action-card"><strong>暂无行动建议</strong><span>当前后端未返回 actions 字段，建议重启后端以加载最新接口。</span></div>}
        </div>
      </section>

      <section className="panel spec-section">
        <h2><CheckCircle size={19} /> 功能成熟度清单</h2>
        <div className="readiness-list grid">
          {status.readiness.map((item) => (
            <div key={item.key}>
              {item.available ? <CheckCircle size={17} className="status-icon-ok" /> : <XCircle size={17} className="status-icon-missing" />}
              <div><strong>{item.label}</strong><span>{item.available ? '已就绪' : '待完善'}</span></div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
