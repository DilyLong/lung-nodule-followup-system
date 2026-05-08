import { ArrowLeft, CheckCircle, FileSpreadsheet, UploadCloud, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { api, commitDatasetImport, fetchImportBatchDetail, fetchImportBatches, fetchPatients, previewDatasetImport, rollbackImportBatch, validateDatasetImport, type ImportBatch, type ImportBatchDetail, type ImportCommitReport, type ImportPreviewReport, type ImportValidationReport, type PatientSummary } from '../lib/api';

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

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '暂无';
}

function parseCounts(batch: ImportBatch) {
  try {
    return JSON.parse(batch.counts_json) as Record<string, number>;
  } catch {
    return {};
  }
}

function countText(batch: ImportBatch) {
  const counts = parseCounts(batch);
  const created = (counts.patients_created ?? 0) + (counts.studies_created ?? 0) + (counts.nodules_created ?? 0) + (counts.measurements_created ?? 0);
  const updated = (counts.patients_updated ?? 0) + (counts.studies_updated ?? 0) + (counts.nodules_updated ?? 0) + (counts.measurements_updated ?? 0);
  return `新增 ${created} / 更新 ${updated}`;
}

function severityText(severity: string) {
  if (severity === 'error') return '错误';
  if (severity === 'warning') return '警告';
  return severity;
}

function ImportBatchHistory({ batches, selectedBatch, onSelect, onRollback }: { batches: ImportBatch[]; selectedBatch: ImportBatchDetail | null; onSelect: (id: number) => void; onRollback: (id: number) => void }) {
  return (
    <section className="upload-panel dataset-validation-panel">
      <div>
        <h2>导入批次历史</h2>
        <p>每次真实导入都会保留批次、质控分、实体明细和回滚状态，便于接入真实队列前审计。</p>
      </div>
      <div className="table-card validation-table">
        <table>
          <thead>
            <tr><th>批次</th><th>状态</th><th>质控分</th><th>记录</th><th>时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.id}>
                <td><strong>#{batch.id}</strong></td>
                <td><span className={`model-status-chip ${batch.status === 'committed' ? 'real' : batch.status === 'rolled_back' ? 'fallback' : 'proxy'}`}>{batch.status}</span></td>
                <td>{batch.qc_score.toFixed(1)}</td>
                <td>{countText(batch)}</td>
                <td><span>{formatDate(batch.committed_at ?? batch.created_at)}</span></td>
                <td>
                  <div className="button-row">
                    <button className="small-action" onClick={() => onSelect(batch.id)}>查看明细</button>
                    <button className="small-action danger" disabled={batch.status !== 'committed'} onClick={() => onRollback(batch.id)}>回滚</button>
                  </div>
                </td>
              </tr>
            ))}
            {batches.length === 0 && <tr><td colSpan={6}><span>暂无导入批次。</span></td></tr>}
          </tbody>
        </table>
      </div>
      {selectedBatch && (
        <div className="table-card validation-table">
          <table>
            <thead><tr><th>类型</th><th>动作</th><th>实体 ID</th><th>稳定键</th></tr></thead>
            <tbody>
              {selectedBatch.entities.map((entity) => (
                <tr key={entity.id}><td>{entity.entity_type}</td><td>{entity.action}</td><td>{entity.entity_id}</td><td><span>{entity.stable_key}</span></td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
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
  const [previewReport, setPreviewReport] = useState<ImportPreviewReport | null>(null);
  const [commitReport, setCommitReport] = useState<ImportCommitReport | null>(null);
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<ImportBatchDetail | null>(null);
  const [validationMessage, setValidationMessage] = useState('');

  useEffect(() => {
    fetchPatients().then((data) => {
      setPatients(data);
      if (!patientId && data[0]) setSelectedPatientId(data[0].id);
    });
    refreshBatches();
  }, [patientId]);

  async function refreshBatches() {
    const data = await fetchImportBatches();
    setBatches(data);
  }


  function buildCsvFormData() {
    const missing = csvInputs.filter((item) => !csvFiles[item.key]).map((item) => item.fileName);
    if (missing.length) {
      setValidationMessage(`请先选择：${missing.join('、')}`);
      return null;
    }
    const formData = new FormData();
    csvInputs.forEach((item) => {
      const selected = csvFiles[item.key];
      if (selected) formData.append(item.key, selected);
    });
    return formData;
  }

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
      const anonymization = data.metadata?.anonymization;
      const suffix = anonymization?.checked ? ` 脱敏检查：${anonymization.safe ? '通过' : `发现 ${anonymization.unsafe_fields.join('、')}`}` : '';
      setMessage(`${data.message}${suffix}`);
    } catch {
      setMessage('上传失败，请确认后端服务已启动。');
    } finally {
      setUploading(false);
    }
  }

  async function handleValidateDataset() {
    const formData = buildCsvFormData();
    if (!formData) return;
    setValidating(true);
    setValidationMessage('');
    setCommitReport(null);
    setPreviewReport(null);
    try {
      const report = await validateDatasetImport(formData);
      setValidationReport(report);
    } catch {
      setValidationMessage('校验失败，请确认后端服务已启动，且 CSV 文件为 UTF-8 编码。');
    } finally {
      setValidating(false);
    }
  }

  async function handlePreviewDataset() {
    const formData = buildCsvFormData();
    if (!formData) return;
    setValidating(true);
    setValidationMessage('');
    setCommitReport(null);
    try {
      const report = await previewDatasetImport(formData);
      setPreviewReport(report);
      setValidationReport(report.validation);
      setValidationMessage(report.message);
    } catch {
      setValidationMessage('预览失败，请确认后端服务已启动，且 CSV 文件仍可读取。');
    } finally {
      setValidating(false);
    }
  }

  async function handleCommitDataset() {
    const formData = buildCsvFormData();
    if (!formData) return;
    setValidating(true);
    setValidationMessage('');
    try {
      const report = await commitDatasetImport(formData);
      setCommitReport(report);
      setValidationReport(report.validation);
      if (report.committed) {
        setValidationMessage(report.message);
        fetchPatients().then(setPatients);
        refreshBatches();
      }
    } catch {
      setValidationMessage('导入失败，请确认后端服务已启动，且 CSV 文件仍可读取。');
    } finally {
      setValidating(false);
    }
  }

  async function handleSelectBatch(batchId: number) {
    setSelectedBatch(await fetchImportBatchDetail(batchId));
  }

  async function handleRollbackBatch(batchId: number) {
    await rollbackImportBatch(batchId);
    setValidationMessage(`已回滚导入批次 #${batchId}。`);
    setSelectedBatch(null);
    await refreshBatches();
    fetchPatients().then(setPatients);
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
          <h2>CSV 数据集校验 / 预览 / 导入</h2>
          <p>上传 patients、studies、nodules、measurements 四张 CSV，先校验字段和跨表关联，再预览新增/更新数量、质控分和风险提示，确认后写入数据库。</p>
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
          <button className="primary" onClick={handleValidateDataset} disabled={validating}><FileSpreadsheet size={17} /> {validating ? '处理中...' : '校验数据集'}</button>
          <button className="ghost" onClick={handlePreviewDataset} disabled={validating || !validationReport?.valid}>预览导入</button>
          <button className="ghost" onClick={handleCommitDataset} disabled={validating || !previewReport?.validation.valid}>确认导入数据库</button>
          <button className="ghost" onClick={() => setPage({ name: 'datasetSpec' })}>查看数据集规范</button>
        </div>
        {validationMessage && <p className={commitReport?.committed ? 'success-banner' : 'info-banner'}>{validationMessage}</p>}
        {previewReport && (
          <div className="validation-summary">
            <div><span>质控分</span><strong>{previewReport.qc_score.toFixed(1)}</strong></div>
            <div><span>患者</span><strong>+{previewReport.counts.patients_created} / 更新 {previewReport.counts.patients_updated}</strong></div>
            <div><span>检查</span><strong>+{previewReport.counts.studies_created} / 更新 {previewReport.counts.studies_updated}</strong></div>
            <div><span>结节/测量</span><strong>+{previewReport.counts.nodules_created + previewReport.counts.measurements_created} / 更新 {previewReport.counts.nodules_updated + previewReport.counts.measurements_updated}</strong></div>
          </div>
        )}
        {previewReport?.qc_issues.length ? (
          <div className="table-card validation-table">
            <table>
              <thead><tr><th>质控级别</th><th>文件</th><th>字段</th><th>提示</th></tr></thead>
              <tbody>
                {previewReport.qc_issues.map((issue, index) => (
                  <tr key={`${issue.file}-${issue.message}-${index}`}><td><span className={`severity-badge ${issue.severity}`}>{severityText(issue.severity)}</span></td><td>{issue.file}</td><td>{issue.column ?? '-'}</td><td><span>{issue.message}</span></td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {commitReport && (
          <div className="validation-summary">
            <div><span>患者</span><strong>+{commitReport.counts.patients_created} / 更新 {commitReport.counts.patients_updated}</strong></div>
            <div><span>检查</span><strong>+{commitReport.counts.studies_created} / 更新 {commitReport.counts.studies_updated}</strong></div>
            <div><span>结节</span><strong>+{commitReport.counts.nodules_created} / 更新 {commitReport.counts.nodules_updated}</strong></div>
            <div><span>测量</span><strong>+{commitReport.counts.measurements_created} / 更新 {commitReport.counts.measurements_updated}</strong></div>
          </div>
        )}
        {validationReport && <ValidationReport report={validationReport} />}
      </section>

      <ImportBatchHistory batches={batches} selectedBatch={selectedBatch} onSelect={handleSelectBatch} onRollback={handleRollbackBatch} />
    </div>
  );
}
