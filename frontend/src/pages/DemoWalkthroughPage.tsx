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
  const [busy, setBusy] = useState<'reset' | 'prepare' | 'standard' | ''>('');
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

  async function handleStandardDemo() {
    setBusy('standard');
    setError('');
    setResetResult(null);
    setPrepareResult(null);
    try {
      const reset = await resetDemoState();
      const prepared = await prepareDemoState();
      setResetResult(reset);
      setPrepareResult(prepared);
      await reloadWalkthrough();
    } catch {
      setError('启动标准演示失败，请确认后端服务已启动并查看后端日志。');
    } finally {
      setBusy('');
    }
  }

  if (error && !walkthrough) {
    return (
      <div className="page">
        <p className="empty">{error}</p>
        <div className="info-banner">请确认当前 8000 端口运行的是最新后端代码；如果刚更新过代码，需要重启 FastAPI 服务。</div>
      </div>
    );
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
          <button className="ghost" onClick={handlePrepare} disabled={busy !== ''}><PlayCircle size={17} /> {busy === 'prepare' ? '生成中...' : '预生成分析和报告'}</button>
          <button className="primary" onClick={handleStandardDemo} disabled={busy !== ''}><RefreshCw size={17} className={busy === 'standard' ? 'spin' : ''} /> {busy === 'standard' ? '启动中...' : '开始标准演示'}</button>
        </div>
      </header>

      <section className="panel safety-panel">
        <h2>{walkthrough.safety_notice.title}</h2>
        <div className="safety-list">
          {walkthrough.safety_notice.items.map((item) => <span key={item}>{item}</span>)}
        </div>
      </section>

      {error && <div className="info-banner">{error}</div>}
      {resetResult && <div className="success-banner"><CheckCircle size={17} /> {resetResult.message} 已清理 {resetResult.cleared.analyses_deleted} 条分析、{resetResult.cleared.reports_deleted} 份报告。</div>}
      {prepareResult && <div className="success-banner"><CheckCircle size={17} /> 已预生成 {prepareResult.created.length} 组代表病例分析和草稿报告，训练样本 {prepareResult.training.eligible_sample_count} 个。</div>}

      <section className="metric-row">
        <div className="metric-card accent"><span>演示就绪度</span><strong>{walkthrough.status.representative_ready_count}/{walkthrough.status.representative_total_count}</strong><p>代表病例已生成报告。</p></div>
        <div className="metric-card"><span>模型训练状态</span><strong>{walkthrough.status.trained ? '已训练' : '未训练'}</strong><p>{walkthrough.status.training_report_exists ? '训练报告已生成。' : `eligible ${walkthrough.readiness.eligible_sample_count}`}</p></div>
        <div className="metric-card"><span>最近报告</span><strong>{walkthrough.status.latest_report_id ? `#${walkthrough.status.latest_report_id}` : '暂无'}</strong><p>{walkthrough.status.latest_report_status ?? '点击开始标准演示后生成。'}</p></div>
      </section>

      <section className="metric-row">
        <div className="metric-card"><span>Synthetic 队列</span><strong>{walkthrough.status.synthetic_patient_count}</strong><p>内置病例用于演示，不含真实患者信息。</p></div>
        <div className="metric-card"><span>阳性 / 阴性</span><strong>{walkthrough.readiness.positive_count} / {walkthrough.readiness.negative_count}</strong><p>用于 JSON 模型训练演示。</p></div>
        <div className="metric-card"><span>分析 / 报告</span><strong>{walkthrough.status.analysis_count} / {walkthrough.status.report_count}</strong><p>标准演示会自动刷新这些状态。</p></div>
      </section>

      <section className="panel spec-section">
        <h2><FileText size={19} /> 推荐点击顺序</h2>
        <div className="demo-route">
          <button className="small-action" onClick={() => setPage({ name: 'systemStatus' })}>1 系统总览</button>
          <span>查看数据质量和最近活动</span>
          <button className="small-action" onClick={() => setPage({ name: 'modelStatus' })}>2 模型状态</button>
          <span>讲解训练结果与自检</span>
          <button className="small-action" onClick={() => setPage({ name: 'patient', patientId: walkthrough.status.representative_stories[0]?.patient_id ?? 1 })}>3 代表病例</button>
          <span>运行目标结节分析</span>
          <button className="small-action" onClick={() => setPage({ name: 'dashboard' })}>4 结构化报告</button>
          <span>从病例页进入报告确认和导出</span>
        </div>
      </section>

      <section className="panel spec-section">
        <h2>代表病例故事线</h2>
        <div className="story-grid">
          {walkthrough.status.representative_stories.map((story) => (
            <article className="story-card" key={story.patient_code}>
              <div>
                <span className="model-status-chip proxy">{story.label}</span>
                <h3>{story.patient_code} · {story.name}</h3>
                <p>{story.headline}</p>
                <small>{story.demo_reason}</small>
              </div>
              <div className="story-meta">
                <span>结节 {story.nodule_count} 个</span>
                <span>{story.latest_risk_level ? `${story.latest_risk_level} ${story.latest_risk_score?.toFixed(2)}` : '待分析'}</span>
                <span>{story.latest_report_id ? `报告 #${story.latest_report_id}` : '待生成报告'}</span>
              </div>
              {story.patient_id && <button className="small-action" onClick={() => setPage({ name: 'patient', patientId: story.patient_id! })}>打开病例</button>}
            </article>
          ))}
        </div>
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
              <thead><tr><th>故事线</th><th>病例</th><th>风险</th><th>分析 ID</th><th>报告 ID</th><th></th></tr></thead>
              <tbody>
                {prepareResult.created.map((item) => (
                  <tr key={item.report_id}>
                    <td>{item.story.label}</td>
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
