import { ArrowLeft, UploadCloud } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { api, fetchPatients, type PatientSummary } from '../lib/api';

interface Props {
  patientId?: number;
  setPage: (page: Page) => void;
}

export default function UploadStudy({ patientId, setPage }: Props) {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState(patientId ?? 1);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetchPatients().then((data) => {
      setPatients(data);
      if (!patientId && data[0]) setSelectedPatientId(data[0].id);
    });
  }, [patientId]);

  async function handleUpload() {
    if (!file) {
      setMessage('请先选择一个 DICOM、NIfTI 或压缩包文件。');
      return;
    }
    const formData = new FormData();
    formData.append('patient_id', String(selectedPatientId));
    formData.append('file', file);
    setUploading(true);
    try {
      const { data } = await api.post('/uploads', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setMessage(data.message);
    } catch (error) {
      setMessage('上传失败，请确认后端服务已启动。');
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Study upload</p>
          <h1>上传多期 CT 检查</h1>
          <span>支持 DICOM 单文件或 zip 序列解析，解析后可浏览 CT 切片并标注 ROI。</span>
        </div>
        <button className="ghost" onClick={() => setPage({ name: 'dashboard' })}><ArrowLeft size={17} /> 返回工作台</button>
      </header>

      <section className="upload-panel">
        <label>
          选择病例
          <select value={selectedPatientId} onChange={(event) => setSelectedPatientId(Number(event.target.value))}>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>{patient.patient_code} · {patient.name}</option>
            ))}
          </select>
        </label>
        <label className="dropzone">
          <UploadCloud size={38} />
          <strong>{file ? file.name : '选择影像文件'}</strong>
          <span>支持 .dcm 或 DICOM zip 序列；解析成功后可进入病例详情浏览切片、标注结节并生成 ROI 测量。</span>
          <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
        <button className="primary" onClick={handleUpload} disabled={uploading}>{uploading ? '上传中...' : '上传检查'}</button>
        {message && <p className="info-banner">{message}</p>}
      </section>
    </div>
  );
}
