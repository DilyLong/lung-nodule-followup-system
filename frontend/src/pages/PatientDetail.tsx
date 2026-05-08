import { Download, FileText, PlayCircle, RefreshCw, Upload } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { Page } from '../App';
import CtSliceViewer from '../components/CtSliceViewer';
import FollowupComparison from '../components/FollowupComparison';
import ModelExplanationPanel from '../components/ModelExplanationPanel';
import RegistrationPanel from '../components/RegistrationPanel';
import NoduleManager from '../components/NoduleManager';
import NoduleMetrics from '../components/NoduleMetrics';
import RiskTrendChart from '../components/RiskTrendChart';
import StudyTimeline from '../components/StudyTimeline';
import { createReport, fetchDemoRepresentativeCases, fetchPatient, cohortTableCsvUrl, measurementsCsvUrl, researchPackageZipUrl, researchTableCsvUrl, runAnalysis, type Analysis, type DemoRepresentativeStory, type Nodule, type PatientDetail as PatientDetailType } from '../lib/api';

function parseModelStatus(analysis?: Analysis) {
  if (!analysis) return null;
  try {
    const features = JSON.parse(analysis.features_json);
    return features.risk?.model_status ?? null;
  } catch {
    return null;
  }
}

function sortedMeasurements(nodule?: Nodule) {
  return [...(nodule?.measurements ?? [])].sort((a, b) => a.study_id - b.study_id);
}

interface Props {
  patientId: number;
  setPage: (page: Page) => void;
}

export default function PatientDetail({ patientId, setPage }: Props) {
  const [patient, setPatient] = useState<PatientDetailType | null>(null);
  const [running, setRunning] = useState(false);
  const [creatingReport, setCreatingReport] = useState(false);
  const [followupRefreshKey, setFollowupRefreshKey] = useState(0);
  const [selectedNoduleId, setSelectedNoduleId] = useState<number | null>(null);
  const [demoStory, setDemoStory] = useState<DemoRepresentativeStory | null>(null);

  async function loadPatient() {
    const data = await fetchPatient(patientId);
    setPatient(data);
  }

  useEffect(() => {
    loadPatient();
  }, [patientId]);

  useEffect(() => {
    if (patient?.nodules.length && !selectedNoduleId) {
      setSelectedNoduleId(patient.nodules[0].id);
    }
  }, [patient, selectedNoduleId]);

  useEffect(() => {
    fetchDemoRepresentativeCases()
      .then((stories) => setDemoStory(stories.find((story) => story.patient_id === patientId) ?? null))
      .catch(() => setDemoStory(null));
  }, [patientId]);

  const nodule = patient?.nodules.find((item) => item.id === selectedNoduleId) ?? patient?.nodules[0];
  const noduleMeasurements = useMemo(() => sortedMeasurements(nodule), [nodule]);
  const firstMeasurement = noduleMeasurements[0];
  const latestMeasurement = noduleMeasurements.at(-1);
  const latestAnalysis: Analysis | undefined = useMemo(() => {
    const exactAnalyses = patient?.analyses.filter((analysis) => analysis.nodule_id === nodule?.id) ?? [];
    if (exactAnalyses.length > 0) return exactAnalyses.at(-1);
    const legacyAnalyses = patient?.analyses.filter((analysis) => analysis.nodule_id == null) ?? [];
    return legacyAnalyses.at(-1);
  }, [patient, nodule]);
  const modelStatus = parseModelStatus(latestAnalysis);

  function handleNoduleCreated(nodule: Nodule) {
    setPatient((current) => current ? { ...current, nodules: [...current.nodules, nodule] } : current);
    setFollowupRefreshKey((value) => value + 1);
  }

  async function handleRunAnalysis() {
    setRunning(true);
    try {
      await runAnalysis(patientId, selectedNoduleId);
      await loadPatient();
    } finally {
      setRunning(false);
    }
  }

  async function handleCreateReport() {
    if (!latestAnalysis) return;
    setCreatingReport(true);
    try {
      await createReport(latestAnalysis.id);
      setPage({ name: 'report', patientId });
    } finally {
      setCreatingReport(false);
    }
  }

  if (!patient) {
    return <div className="page"><p className="empty">正在加载病例详情...</p></div>;
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Patient detail</p>
          <h1>{patient.name} · {patient.patient_code}</h1>
          <span>{patient.sex}，{patient.age} 岁，{patient.primary_diagnosis}</span>
        </div>
        <div className="button-row">
          <a className="ghost" href={researchPackageZipUrl(patient.id)}><Download size={17} /> 导出本病例数据包</a>
          <a className="ghost" href={cohortTableCsvUrl(patient.id)}><Download size={17} /> 导出本病例基础队列表</a>
          <a className="ghost" href={researchTableCsvUrl(patient.id)}><Download size={17} /> 导出本病例研究表</a>
          <a className="ghost" href={measurementsCsvUrl(patient.id)}><Download size={17} /> 导出本病例测量表</a>
          <button className="ghost" onClick={() => setPage({ name: 'upload', patientId })}><Upload size={17} /> 上传检查</button>
          <button className="primary" onClick={handleRunAnalysis} disabled={running || !selectedNoduleId}>
            {running ? <RefreshCw size={17} className="spin" /> : <PlayCircle size={17} />} 运行目标结节分析
          </button>
        </div>
      </header>

      {demoStory && (
        <section className="panel demo-story-panel">
          <div>
            <span className="model-status-chip proxy">{demoStory.label}</span>
            <h2>{demoStory.headline}</h2>
            <p>{demoStory.demo_reason}</p>
          </div>
          <div className="story-meta">
            <span>演示病例 {demoStory.patient_code}</span>
            <span>{demoStory.nodule_count} 个结节</span>
            <span>{demoStory.latest_report_id ? `已有报告 #${demoStory.latest_report_id}` : '可生成报告'}</span>
          </div>
        </section>
      )}

      <section className="panel">
        <h2>多结节管理</h2>
        <NoduleManager
          patientId={patient.id}
          nodules={patient.nodules}
          selectedNoduleId={selectedNoduleId}
          onSelect={(id) => setSelectedNoduleId(id)}
          onCreated={handleNoduleCreated}
        />
      </section>

      <section className="detail-grid">
        <div className="panel wide">
          <h2>多期 CT 时间轴</h2>
          <StudyTimeline studies={patient.studies} />
        </div>
        <div className="panel">
          <h2>目标结节</h2>
          <p className="large-text">{nodule?.nodule_type}</p>
          <p>{nodule?.lobe}</p>
          <span>{nodule ? `${nodule.label} · ${nodule.baseline_impression}` : '暂无目标结节'}</span>
        </div>
      </section>

      <section className="metric-row">
        <NoduleMetrics title="基线" measurement={firstMeasurement} />
        <NoduleMetrics title="最近一次" measurement={latestMeasurement} />
        <div className="metric-card accent">
          <span>AI 风险分层</span>
          <strong>{latestAnalysis?.risk_level ?? '该结节待分析'}</strong>
          <p>{latestAnalysis ? `目标结节风险评分 ${latestAnalysis.risk_score.toFixed(2)}，配准质量 ${latestAnalysis.registration_quality.toFixed(2)}` : '选择目标结节并运行分析后生成独立风险评分。'}</p>
          {latestAnalysis && <span className={`model-status-chip ${modelStatus?.startsWith('real_') ? 'real' : modelStatus?.startsWith('fallback_') ? 'fallback' : 'proxy'}`}>{modelStatus ?? '模型未记录'}</span>}
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel wide"><RiskTrendChart measurements={noduleMeasurements} /></div>
        <div className="panel">
          <h2>AI 时序模型解释</h2>
          <ModelExplanationPanel analysis={latestAnalysis} />
        </div>
      </section>

      <section className="panel">
        <h2>真实三维配准</h2>
        <RegistrationPanel analysis={latestAnalysis} />
      </section>

      <section className="panel">
        <h2>真实 DICOM CT 切片浏览器</h2>
        <CtSliceViewer
          studies={patient.studies}
          patientId={patient.id}
          nodules={patient.nodules}
          selectedNoduleId={selectedNoduleId}
          onMeasurementChanged={() => setFollowupRefreshKey((value) => value + 1)}
        />
      </section>

      <section className="panel">
        <h2>标注生成的多期随访测量</h2>
        <FollowupComparison patientId={patient.id} noduleId={selectedNoduleId} refreshKey={followupRefreshKey} />
      </section>

      {latestAnalysis && (
        <section className="panel report-summary">
          <div>
            <h2>个体化随访建议</h2>
            <p>{latestAnalysis.recommendation}</p>
            <div className="analysis-grid">
              <span>最大径变化：<b>{latestAnalysis.diameter_change_mm.toFixed(1)} mm</b></span>
              <span>体积变化：<b>{latestAnalysis.volume_change_percent.toFixed(1)}%</b></span>
              <span>密度变化：<b>{latestAnalysis.density_change_hu.toFixed(1)} HU</b></span>
              <span>倍增时间：<b>{latestAnalysis.volume_doubling_time_days ?? '未达到倍增'} 天</b></span>
            </div>
          </div>
          <button className="primary" onClick={handleCreateReport} disabled={creatingReport}>
            <FileText size={17} /> 生成结构化报告
          </button>
        </section>
      )}
    </div>
  );
}
