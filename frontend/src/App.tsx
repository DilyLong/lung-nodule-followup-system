import { Activity, BrainCircuit, Database, FileText, FolderTree, Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import Dashboard from './pages/Dashboard';
import DatasetSpecification from './pages/DatasetSpecification';
import ModelStatusPage from './pages/ModelStatusPage';
import PatientDetail from './pages/PatientDetail';
import ReportView from './pages/ReportView';
import UploadStudy from './pages/UploadStudy';

export type Page =
  | { name: 'dashboard' }
  | { name: 'patient'; patientId: number }
  | { name: 'upload'; patientId?: number }
  | { name: 'datasetSpec' }
  | { name: 'modelStatus' }
  | { name: 'report'; patientId: number };

export default function App() {
  const [page, setPage] = useState<Page>({ name: 'dashboard' });

  useEffect(() => {
    document.title = '肺结节多期 CT 智能随访系统';
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Activity size={26} />
          <div>
            <strong>肺结节智能随访</strong>
            <span>CT 时序分析 MVP</span>
          </div>
        </div>
        <nav>
          <button className={page.name === 'dashboard' ? 'active' : ''} onClick={() => setPage({ name: 'dashboard' })}>
            <Database size={18} /> 病例工作台
          </button>
          <button className={page.name === 'upload' ? 'active' : ''} onClick={() => setPage({ name: 'upload' })}>
            <Upload size={18} /> 影像上传
          </button>
          <button className={page.name === 'datasetSpec' ? 'active' : ''} onClick={() => setPage({ name: 'datasetSpec' })}>
            <FolderTree size={18} /> 数据集规范
          </button>
          <button className={page.name === 'modelStatus' ? 'active' : ''} onClick={() => setPage({ name: 'modelStatus' })}>
            <BrainCircuit size={18} /> 模型状态
          </button>
          <button disabled>
            <FileText size={18} /> 结构化报告
          </button>
        </nav>
        <div className="sidebar-note">
          当前为本地演示版：算法接口已预留，可替换真实 DICOM 配准与 ConvLSTM 模型。
        </div>
      </aside>
      <main className="main-panel">
        {page.name === 'dashboard' && <Dashboard setPage={setPage} />}
        {page.name === 'patient' && <PatientDetail patientId={page.patientId} setPage={setPage} />}
        {page.name === 'upload' && <UploadStudy patientId={page.patientId} setPage={setPage} />}
        {page.name === 'datasetSpec' && <DatasetSpecification setPage={setPage} />}
        {page.name === 'modelStatus' && <ModelStatusPage setPage={setPage} />}
        {page.name === 'report' && <ReportView patientId={page.patientId} setPage={setPage} />}
      </main>
    </div>
  );
}
