import { ArrowLeft, CheckCircle, FolderTree } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page } from '../App';
import { fetchImportSpec, type ImportSpec } from '../lib/api';

interface Props {
  setPage: (page: Page) => void;
}

function renderValueList(values: string[]) {
  return values.map((value) => <span className="spec-tag" key={value}>{value}</span>);
}

export default function DatasetSpecification({ setPage }: Props) {
  const [spec, setSpec] = useState<ImportSpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchImportSpec()
      .then(setSpec)
      .catch(() => setError('无法读取数据集规范，请确认后端服务已启动。'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="page"><p className="empty">正在读取真实数据准备规范...</p></div>;
  }

  if (error || !spec) {
    return <div className="page"><p className="empty">{error || '暂无数据集规范。'}</p></div>;
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Dataset readiness</p>
          <h1>数据集规范 / 真实数据准备</h1>
          <span>按统一 DICOM 目录、CSV 字段和标签规范整理数据，便于后续训练、统计和回顾性分析。</span>
        </div>
        <div className="button-row">
          <button className="primary" onClick={() => setPage({ name: 'upload' })}>去校验 CSV 数据集</button>
          <button className="ghost" onClick={() => setPage({ name: 'dashboard' })}><ArrowLeft size={17} /> 返回工作台</button>
        </div>
      </header>

      <section className="stat-grid">
        <div className="stat-card"><span>规范版本</span><strong>{spec.spec_version}</strong></div>
        <div className="stat-card"><span>日期格式</span><strong>{spec.date_format}</strong></div>
        <div className="stat-card"><span>CSV 文件</span><strong>{Object.keys(spec.files).length}</strong></div>
      </section>

      <section className="panel spec-section">
        <h2><FolderTree size={19} /> DICOM 多期 CT 目录</h2>
        <div className="spec-kv-grid">
          {Object.entries(spec.dicom_layout).map(([key, value]) => (
            <div key={key}>
              <span>{key}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="panel spec-section">
        <h2>坐标、单位与 ROI 约定</h2>
        <div className="spec-kv-grid">
          {Object.entries(spec.coordinate_system).map(([key, value]) => (
            <div key={key}>
              <span>{key}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="panel spec-section">
        <h2>CSV 文件与字段</h2>
        <div className="table-card spec-table-card">
          <table>
            <thead>
              <tr>
                <th>文件</th>
                <th>必填字段</th>
                <th>可选字段</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(spec.files).map(([fileName, fileSpec]) => (
                <tr key={fileName}>
                  <td><strong>{fileName}</strong></td>
                  <td><div className="spec-tag-list">{renderValueList(fileSpec.required_columns)}</div></td>
                  <td><div className="spec-tag-list">{renderValueList(fileSpec.optional_columns)}</div></td>
                  <td><span>{fileSpec.notes}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel spec-section">
          <h2>标签枚举</h2>
          <div className="spec-enum-list">
            {Object.entries(spec.allowed_values).map(([field, values]) => (
              <div key={field}>
                <strong>{field}</strong>
                <div className="spec-tag-list">{renderValueList(values)}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel spec-section">
          <h2>质控规则</h2>
          <div className="spec-check-list">
            {spec.quality_checks.map((item) => (
              <p key={item}><CheckCircle size={16} /> {item}</p>
            ))}
          </div>
        </div>
      </section>

      <div className="info-banner">
        批量导入接口状态：{spec.future_import_endpoint.planned ? '已规划' : '未规划'}。{spec.future_import_endpoint.scope}
      </div>
    </div>
  );
}
