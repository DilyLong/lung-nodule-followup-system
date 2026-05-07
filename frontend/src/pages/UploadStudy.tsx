import { ArrowLeft, CheckCircle, FileSpreadsheet, UploadCloud, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { api, fetchPatients, validateDatasetImport, type ImportValidationReport, type PatientSummary } from '../lib/api';

interface Props {
  patientId?: number;
  setPage: (page: Page) => void;
}

type CsvKey = 'patients' | 'studies' | 'nodules' | 'measurements';

const csvInputs: Array<{ key: CsvKey; label: string; fileName: string }> = [
  { key: 'patients', label: '患者表', fileName: 'patients.csv' },
  { key: 'studies', label: '检查表', fileName: 'studies.csv' },
  { key: 'nodules', label: '结节表', fileName: 'nodules.csv' },
  { key: 'measurements', label: '测量表', fileName: 'measurements.csv' },
];

function severityText(severity: string) {
  if (severity === 'error') return '错误';
  if (severity === 'warning') return '警告';
  return severity;
}

function ValidationReport({ report }: { report: ImportValidationReport }) {
  return (
    <div className="validation-report">
      <div className={report.valid ? 'success-banner' : 'info-banner'}>
        {report.valid ? <CheckCircle size={18} /> : <XCircle size={18} />}
        {report.valid ? 'CSV 数据集校验通过，可以进入后续整理或导入步骤。' : 'CSV 数据集存在需要修正的问题，请根据下方报告调整。'}
      </div>
      <div className="validation-summary">
        <div><span>文件数</span><strong>{report.summary.file_count}</strong></div>
        <div><span>总行数</span><strong>{report.summary.total_rows}</strong></div>
        <div><span>错误</span><strong>{report.summary.error_count}</strong></div>
        <div><span>警告</span><strong>{report.summary.warning_count}</strong></div>
      </div>
      <div className="table-card validation-table">
        <table>
          <thead>
            <tr>
              <th>文件</th>
              <th>行数</th>
              <th>缺失必填字段</th>
              <th>未知字段</th>
            </tr>
          </thead>
          <tbody>
            {report.files.map((file) => (
              <tr key={file.file}>
                <td><strong>{file.file}</strong></td>
                <td>{file.row_count}</td>
                <td><span>{file.missing_required_columns.length ? file.missing_required_columns.join('、') : '-'}</span></td>
                <td><span>{file.unknown_columns.length ? file.unknown_columns.join('、') : '-'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-card validation-table">
        <table>
          <thead>
            <tr>
              <th>级别</th>
              <th>文件</th>
              <th>行</th>
              <th>字段</th>
              <th>信息</th>
            </tr>
          </thead>
          <tbody>
            {report.issues.map((issue, index) => (
              <tr key={`${issue.file}-${issue.row}-${issue.column}-${index}`}>
                <td><span className={`severity-badge ${issue.severity}`}>{severityText(issue.severity)}</span></td>
                <td>{issue.file}</td>
                <td>{issue.row ?? '-'}</td>
                <td>{issue.column ?? '-'}</td>
                <td><span>{issue.message}</span></td>
              </tr>
            ))}
            {report.issues.length === 0 && (
              <tr><td colSpan={5}><span>暂无问题。</span></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function UploadStudy({ patientId, setPage }: Props) {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState(patientId ?? 1);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);
  const [csvFiles, setCsvFiles] = useState<Record<CsvKey, File | null>>({ patients: null, studies: null, nodules: null, measurements: null });
  const [validating, setValidating] = useState(false);
  const [validationReport, setValidationReport] = useState<ImportValidationReport | null>(null);
  const [validationMessage, setValidationMessage] = useState('');

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

  async function handleValidateDataset() {
    const missing = csvInputs.filter((item) => !csvFiles[item.key]).map((item) => item.fileName);
    if (missing.length) {
      setValidationMessage(`请先选择：${missing.join('、')}`);
      return;
    }
    const formData = new FormData();
    csvInputs.forEach((item) => {
      const selected = csvFiles[item.key];
      if (selected) formData.append(item.key, selected);
    });
    setValidating(true);
    setValidationMessage('');
    try {
      const report = await validateDatasetImport(formData);
      setValidationReport(report);
    } catch (error) {
      setValidationMessage('校验失败，请确认后端服务已启动，且 CSV 文件为 UTF-8 编码。');
    } finally {
      setValidating(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Study upload</p>
          <h1>上传多期 CT 检查</h1>
          <span>支持 DICOM 单文件或 zip 序列解析；也可先校验真实数据 CSV 是否符合导入规范。</span>
        </div>
        <button className="ghost" onClick={() => setPage({ name: 'dashboard' })}><ArrowLeft size={17} /> 返回工作台</button>
      </header>

      <section className="upload-panel">
        <h2>影像上传</h2>
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

      <section className="upload-panel dataset-validation-panel">
        <div>
          <h2>CSV 数据集校验</h2>
          <p>上传 patients、studies、nodules、measurements 四张 CSV，系统只做字段、枚举、日期、数值和跨表关联校验，不写入数据库。</p>
        </div>
        <div className="csv-input-grid">
          {csvInputs.map((item) => (
            <label key={item.key}>
              {item.label}（{item.fileName}）
              <input type="file" accept=".csv,text/csv" onChange={(event) => setCsvFiles((current) => ({ ...current, [item.key]: event.target.files?.[0] ?? null }))} />
              <span>{csvFiles[item.key]?.name ?? '未选择文件'}</span>
            </label>
          ))}
        </div>
        <div className="button-row">
          <button className="primary" onClick={handleValidateDataset} disabled={validating}><FileSpreadsheet size={17} /> {validating ? '校验中...' : '校验数据集'}</button>
          <button className="ghost" onClick={() => setPage({ name: 'datasetSpec' })}>查看数据集规范</button>
        </div>
        {validationMessage && <p className="info-banner">{validationMessage}</p>}
        {validationReport && <ValidationReport report={validationReport} />}
      </section>
    </div>
  );
}
