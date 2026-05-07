import { AlertTriangle, ChevronRight, Clock, Download, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { Page } from '../App';
import { fetchPatients, cohortTableCsvUrl, measurementsCsvUrl, researchPackageZipUrl, researchTableCsvUrl, type PatientSummary } from '../lib/api';

interface Props {
  setPage: (page: Page) => void;
}

export default function Dashboard({ setPage }: Props) {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPatients()
      .then(setPatients)
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return patients.filter((patient) => {
      const text = `${patient.patient_code}${patient.name}${patient.primary_diagnosis}${patient.nodule_type}`;
      return text.toLowerCase().includes(query.toLowerCase());
    });
  }, [patients, query]);

  const highRisk = patients.filter((patient) => patient.latest_risk_level === '高风险').length;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Clinical workstation</p>
          <h1>肺结节多期 CT 智能随访工作台</h1>
          <span>面向胸外科门诊随访的病例管理、时序分析和个体化建议原型。</span>
        </div>
        <div className="button-row">
          <a className="ghost" href={researchPackageZipUrl()}><Download size={17} /> 导出研究数据包</a>
          <a className="ghost" href={cohortTableCsvUrl()}><Download size={17} /> 导出基础队列表</a>
          <a className="ghost" href={researchTableCsvUrl()}><Download size={17} /> 导出全队列研究表</a>
          <a className="ghost" href={measurementsCsvUrl()}><Download size={17} /> 导出全队列测量表</a>
          <button className="primary" onClick={() => setPage({ name: 'upload' })}>上传新检查</button>
        </div>
      </header>

      <section className="stat-grid">
        <div className="stat-card"><span>演示病例</span><strong>{patients.length}</strong></div>
        <div className="stat-card"><span>已完成 AI 分析</span><strong>{patients.filter((p) => p.latest_risk_level).length}</strong></div>
        <div className="stat-card warning"><span>高风险提示</span><strong>{highRisk}</strong></div>
      </section>

      <div className="toolbar">
        <Search size={18} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索病例编号、姓名、诊断或结节类型" />
      </div>

      <section className="table-card">
        {loading ? (
          <p className="empty">正在加载病例数据...</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>病例</th>
                <th>基本信息</th>
                <th>结节类型</th>
                <th>最近随访</th>
                <th>风险</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((patient) => (
                <tr key={patient.id} onClick={() => setPage({ name: 'patient', patientId: patient.id })}>
                  <td><strong>{patient.patient_code}</strong><br /><span>{patient.name}</span></td>
                  <td>{patient.sex} · {patient.age} 岁<br /><span>{patient.smoking_history}</span></td>
                  <td>{patient.nodule_type ?? '未记录'}<br /><span>{patient.primary_diagnosis}</span></td>
                  <td><Clock size={14} /> {patient.latest_study_date ?? '暂无'}</td>
                  <td>
                    <span className={`risk-pill ${patient.latest_risk_level ?? 'none'}`}>
                      {patient.latest_risk_level ?? '待分析'} {patient.latest_risk_score ? patient.latest_risk_score.toFixed(2) : ''}
                    </span>
                  </td>
                  <td><ChevronRight size={18} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="info-banner">
        <AlertTriangle size={18} /> 第一版使用模拟数据跑通工作流；真实 DICOM、三维配准和 ConvLSTM 模型接口已经在后端预留。
      </div>
    </div>
  );
}
