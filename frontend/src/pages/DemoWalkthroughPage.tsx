import { ArrowLeft, CheckCircle, FileText, PlayCircle, RefreshCw, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { fetchDemoWalkthrough, prepareDemoState, resetDemoState, type DemoPrepareResult, type DemoResetResult, type DemoWalkthrough } from '../lib/api';

interface Props {
  setPage: (page: Page) => void;
}

export default function DemoWalkthroughPage({ setPage }: Props) {
  const [walkthrough, setWalkthrough] = useState<DemoWalkthrough | null>(null);
  const [resetResult, setResetResult] = useState<DemoResetResult | null>(null);
  const [prepareResult, setPrepareResult] = useState<DemoPrepareResult | null>(null);
  const [busy, setBusy] = useState<'reset' | 'prepare' | ''>('');
  const [error, setError] = useState('');

  async function reloadWalkthrough() {
    const data = await fetchDemoWalkthrough();
    setWalkthrough(data);
  }

  useEffect(() => {
    reloadWalkthrough().catch(() => setError('无法读取演示脚本，请确认后端服务已启动。'));
  }, []);

  async function handleReset() {
    setBusy('reset');
    setError('');
    try {
      const result = await resetDemoState();
      setResetResult(result);
      setPrepareResult(null);
      await reloadWalkthrough();
    } catch {
      setError('一键重置演示状态失败，请查看后端日志。');
    } finally {
      setBusy('');
    }
  }

  async function handlePrepare() {
    setBusy('prepare');
    setError('');
    try {
      const result = await prepareDemoState();
      setPrepareResult(result);
      await reloadWalkthrough();
    } catch {
      setError('预生成分析和报告失败，请查看后端日志。');
    } finally {
      setBusy('');
    }
  }

  if (!walkthrough) {
    return <div className="page"><p className="empty">正在加载演示脚本...</p></div>;
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Demo walkthrough</p>
          <h1>{walkthrough.title}</h1>
          <span>{walkthrough.summary}</span>
        </div>
        <div className="button-row">
          <button className="ghost" onClick={() => setPage({ name: 'dashboard' })}><ArrowLeft size={17} /> 返回工作台</button>
          <button className="ghost" onClick={handleReset} disabled={busy !== ''}><RotateCcw size={17} /> {busy === 'reset' ? '重置中...' : '一键重置演示状态'}</button>
          <button className="primary" onClick={handlePrepare} disabled={busy !== ''}><PlayCircle size={17} /> {busy === 'prepare' ? '生成中...' : '预生成分析和报告'}</button>
        </div>
      </header>

      {error && <div className="info-banner">{error}</div>}
      {resetResult && <div className="success-banner"><CheckCircle size={17} /> {resetResult.message} 已清理 {resetResult.cleared.analyses_deleted} 条分析、{resetResult.cleared.reports_deleted} 份报告。</div>}
      {prepareResult && <div className="success-banner"><CheckCircle size={17} /> 已预生成 {prepareResult.created.length} 组代表病例分析和草稿报告，训练样本 {prepareResult.training.eligible_sample_count} 个。</div>}

      <section className="metric-row">
        <div className="metric-card accent"><span>演示队列状态</span><strong>{walkthrough.readiness.ready ? '可训练' : '需补数据'}</strong><p>eligible {walkthrough.readiness.eligible_sample_count}</p></div>
        <div className="metric-card"><span>阳性 / 阴性</span><strong>{walkthrough.readiness.positive_count} / {walkthrough.readiness.negative_count}</strong><p>用于 JSON 模型训练演示。</p></div>
        <div className="metric-card"><span>已排除样本</span><strong>{walkthrough.readiness.excluded_count}</strong><p>查看系统总览的数据质量看板。</p></div>
      </section>

      <section className="panel spec-section">
        <h2><FileText size={19} /> 演示讲解路径</h2>
        <div className="demo-step-list">
          {walkthrough.steps.map((step) => (
            <div className="demo-step" key={step.order}>
              <strong>{step.order}</strong>
              <div>
                <span>{step.page}</span>
                <h3>{step.action}</h3>
                <p>{step.expected}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {prepareResult && (
        <section className="panel spec-section">
          <h2>预生成代表病例</h2>
          <div className="table-card validation-table">
            <table>
              <thead><tr><th>病例</th><th>风险</th><th>分析 ID</th><th>报告 ID</th><th></th></tr></thead>
              <tbody>
                {prepareResult.created.map((item) => (
                  <tr key={item.report_id}>
                    <td>{item.patient_code}</td>
                    <td><span className={`risk-pill ${item.risk_level}`}>{item.risk_level} {item.risk_score.toFixed(2)}</span></td>
                    <td>{item.analysis_id}</td>
                    <td>{item.report_id}</td>
                    <td><button className="small-action" onClick={() => setPage({ name: 'patient', patientId: item.patient_id })}>打开病例</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="action-grid">
        <div className="action-card"><strong>下一站：系统总览</strong><span>查看数据质量看板、最近分析和最近报告。</span><button className="small-action" onClick={() => setPage({ name: 'systemStatus' })}>打开系统总览</button></div>
        <div className="action-card"><strong>下一站：模型状态</strong><span>运行队列训练和模型自检，展示 JSON 模型闭环。</span><button className="small-action" onClick={() => setPage({ name: 'modelStatus' })}>打开模型状态</button></div>
        <div className="action-card"><strong>下一站：病例工作台</strong><span>选择代表病例，展示目标结节分析和报告生成。</span><button className="small-action" onClick={() => setPage({ name: 'dashboard' })}>打开病例工作台</button></div>
      </section>
    </div>
  );
}
