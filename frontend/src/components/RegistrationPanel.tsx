import { registrationPreviewUrl, type Analysis } from '../lib/api';

interface Props {
  analysis?: Analysis;
}

interface RegistrationTransform {
  study_id: number;
  translation_voxel?: number[];
  before_correlation?: number | null;
  after_correlation?: number | null;
}

interface RegistrationPreview {
  fixed_study_id: number;
  moving_study_id: number;
  path: string;
  before_correlation?: number | null;
  after_correlation?: number | null;
}

interface RegistrationPayload {
  method?: string;
  status?: string;
  reason?: string;
  registration_quality?: number;
  reference_study_id?: number | null;
  transforms?: RegistrationTransform[];
  previews?: RegistrationPreview[];
}

function parseRegistration(analysis?: Analysis): RegistrationPayload | null {
  if (!analysis) return null;
  try {
    const features = JSON.parse(analysis.features_json);
    return features.registration ?? null;
  } catch {
    return null;
  }
}

function formatCorrelation(value?: number | null) {
  return value == null ? '-' : value.toFixed(3);
}

function formatTranslation(values?: number[]) {
  if (!values?.length) return '-';
  const [z, y, x] = values;
  return `Z ${z?.toFixed(1) ?? '-'} / Y ${y?.toFixed(1) ?? '-'} / X ${x?.toFixed(1) ?? '-'} voxel`;
}

export default function RegistrationPanel({ analysis }: Props) {
  const registration = parseRegistration(analysis);

  if (!analysis) {
    return <p className="empty compact">点击“运行时序分析”后生成配准质量评分和真实 DICOM 配准预览。</p>;
  }

  if (!registration) {
    return <p className="empty compact">该次分析没有配准详情，请重新运行时序分析。</p>;
  }

  const isReal = registration.status === 'real_dicom';

  return (
    <div className="registration-panel">
      <div className="registration-summary">
        <div><span>配准状态</span><strong>{isReal ? '真实 DICOM 配准' : '占位评分'}</strong></div>
        <div><span>质量评分</span><strong>{(registration.registration_quality ?? analysis.registration_quality).toFixed(3)}</strong></div>
        <div><span>参考检查</span><strong>{registration.reference_study_id ?? '-'}</strong></div>
      </div>
      <p className="registration-method">
        方法：{registration.method ?? '未知'}{registration.reason ? `；${registration.reason}` : ''}
      </p>

      {registration.previews?.length ? (
        <div className="registration-preview-grid">
          {registration.previews.map((preview) => (
            <figure className="registration-preview" key={preview.path}>
              <img src={registrationPreviewUrl(preview.path)} alt={`Registration preview ${preview.moving_study_id}`} />
              <figcaption>
                Study {preview.fixed_study_id} → {preview.moving_study_id}；相关性 {formatCorrelation(preview.before_correlation)} → {formatCorrelation(preview.after_correlation)}
              </figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <p className="empty compact">暂无真实配准预览图；上传至少两期真实 DICOM 后重新运行时序分析。</p>
      )}

      {registration.transforms?.length ? (
        <table className="registration-table">
          <thead>
            <tr>
              <th>检查 ID</th>
              <th>平移量</th>
              <th>配准前相关性</th>
              <th>配准后相关性</th>
            </tr>
          </thead>
          <tbody>
            {registration.transforms.map((transform) => (
              <tr key={transform.study_id}>
                <td>{transform.study_id}</td>
                <td>{formatTranslation(transform.translation_voxel)}</td>
                <td>{formatCorrelation(transform.before_correlation)}</td>
                <td>{formatCorrelation(transform.after_correlation)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
