import { ChevronLeft, ChevronRight, Image as ImageIcon, Link2, RefreshCw, Trash2 } from 'lucide-react';
import { MouseEvent, useEffect, useMemo, useState } from 'react';
import {
  createPatientNodule,
  confirmAnnotationMatch,
  createMeasurementFromAnnotation,
  createNoduleAnnotation,
  deleteNoduleAnnotation,
  fetchMatchCandidates,
  fetchStudyAnnotations,
  fetchStudyImageSeries,
  sliceImageUrl,
  type MatchCandidate,
  type Nodule,
  type NoduleAnnotation,
  type Study,
  type StudyImageSeries,
} from '../lib/api';

interface Props {
  studies: Study[];
  patientId: number;
  onMeasurementChanged?: () => void;
  nodules: Nodule[];
  selectedNoduleId: number | null;
}

interface DraftAnnotation {
  x_percent: number;
  y_percent: number;
}

export default function CtSliceViewer({ studies, patientId, onMeasurementChanged, nodules, selectedNoduleId }: Props) {
  const studiesWithSlices = studies.filter((study) => study.slices.length > 0 || study.status.includes('DICOM'));
  const [studyId, setStudyId] = useState<number | null>(studiesWithSlices[0]?.id ?? null);
  const [series, setSeries] = useState<StudyImageSeries | null>(null);
  const [sliceIndex, setSliceIndex] = useState(0);
  const [annotations, setAnnotations] = useState<NoduleAnnotation[]>([]);
  const [draft, setDraft] = useState<DraftAnnotation | null>(null);
  const [diameterMm, setDiameterMm] = useState('8');
  const [noduleType, setNoduleType] = useState('磨玻璃结节');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [measurementMessage, setMeasurementMessage] = useState('');
  const [candidateAnnotationId, setCandidateAnnotationId] = useState<number | null>(null);
  const [matchCandidates, setMatchCandidates] = useState<MatchCandidate[]>([]);
  const [windowCenter, setWindowCenter] = useState(0);
  const [windowWidth, setWindowWidth] = useState(100);

  useEffect(() => {
    const firstId = studiesWithSlices[0]?.id ?? null;
    setStudyId((current) => current ?? firstId);
  }, [studies.length]);

  async function loadAnnotations(nextStudyId: number) {
    const data = await fetchStudyAnnotations(nextStudyId);
    setAnnotations(data);
  }

  useEffect(() => {
    if (!studyId) return;
    setError('');
    setDraft(null);
    fetchStudyImageSeries(studyId)
      .then(async (data) => {
        setSeries(data);
        setSliceIndex(Math.floor(Math.max(data.slices.length - 1, 0) / 2));
        setWindowCenter(data.window_center ?? 0);
        setWindowWidth(data.window_width ?? 100);
        await loadAnnotations(studyId);
      })
      .catch(() => {
        setSeries(null);
        setAnnotations([]);
        setError('该检查暂无可浏览 DICOM 切片，请上传真实 DICOM 或 zip 序列。');
      });
  }, [studyId]);

  const currentSlice = useMemo(() => {
    if (!series?.slices.length) return null;
    return series.slices[Math.min(sliceIndex, series.slices.length - 1)];
  }, [series, sliceIndex]);

  const currentAnnotations = useMemo(() => {
    if (!currentSlice) return [];
    return annotations.filter((annotation) => annotation.slice_id === currentSlice.id);
  }, [annotations, currentSlice]);

  function handleImageClick(event: MouseEvent<HTMLDivElement>) {
    if (!currentSlice) return;
    const target = event.currentTarget;
    const rect = target.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    setDraft({ x_percent: Math.max(0, Math.min(100, x)), y_percent: Math.max(0, Math.min(100, y)) });
  }

  async function handleSaveAnnotation() {
    if (!currentSlice || !studyId || !draft) return;
    const parsedDiameter = Number(diameterMm);
    if (!Number.isFinite(parsedDiameter) || parsedDiameter <= 0) {
      setError('请输入有效的结节最大径。');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await createNoduleAnnotation({
        patient_id: patientId,
        study_id: studyId,
        slice_id: currentSlice.id,
        nodule_id: selectedNoduleId,
        x_percent: draft.x_percent,
        y_percent: draft.y_percent,
        diameter_mm: parsedDiameter,
        nodule_type: noduleType,
        note,
      });
      await loadAnnotations(studyId);
      setDraft(null);
      setNote('');
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAnnotation(annotationId: number) {
    if (!studyId) return;
    await deleteNoduleAnnotation(annotationId);
    await loadAnnotations(studyId);
  }

  function formatMeasurementMessage(result: Awaited<ReturnType<typeof createMeasurementFromAnnotation>>) {
    const { measurement } = result;
    const roiRange = measurement.min_hu != null && measurement.max_hu != null
      ? `，ROI ${measurement.min_hu.toFixed(0)}~${measurement.max_hu.toFixed(0)} HU`
      : '';
    const roiArea = measurement.roi_area_mm2 != null ? `，面积 ${measurement.roi_area_mm2.toFixed(1)} mm²` : '';
    return `${result.message} 平均 ${measurement.mean_hu.toFixed(0)} HU${roiRange}${roiArea}，实性 ${measurement.solid_component_percent.toFixed(0)}%。`;
  }

  async function handleCreateMeasurement(annotationId: number) {
    if (!studyId) return;
    const result = await createMeasurementFromAnnotation(annotationId);
    setMeasurementMessage(formatMeasurementMessage(result));
    await loadAnnotations(studyId);
    onMeasurementChanged?.();
    return result;
  }

  async function handleShowCandidates(annotationId: number) {
    if (candidateAnnotationId === annotationId) {
      setCandidateAnnotationId(null);
      setMatchCandidates([]);
      return;
    }
    const candidates = await fetchMatchCandidates(annotationId);
    setCandidateAnnotationId(annotationId);
    setMatchCandidates(candidates);
  }

  async function handleConfirmCandidate(annotationId: number, noduleId: number) {
    if (!studyId) return;
    await confirmAnnotationMatch(annotationId, noduleId);
    const result = await handleCreateMeasurement(annotationId);
    setMeasurementMessage(result ? formatMeasurementMessage(result) : '已确认该标注对应既往结节。');
    setCandidateAnnotationId(null);
    setMatchCandidates([]);
    await loadAnnotations(studyId);
  }

  function clampSlice(index: number) {
    return Math.max(0, Math.min(index, (series?.slices.length ?? 1) - 1));
  }

  function imageFilter() {
    const contrast = Math.max(60, Math.min(220, 15000 / Math.max(windowWidth, 1)));
    const brightness = Math.max(50, Math.min(180, 100 + windowCenter / 12));
    return { filter: `contrast(${contrast.toFixed(0)}%) brightness(${brightness.toFixed(0)}%)` };
  }

  async function handleCreateNewNodule(annotation: NoduleAnnotation) {
    const nodule = await createPatientNodule(patientId, {
      label: `新结节-${annotation.id}`,
      lobe: '待医生确认',
      nodule_type: annotation.nodule_type,
      baseline_impression: annotation.note || '由跨期标注工作流创建',
    });
    await handleConfirmCandidate(annotation.id, nodule.id);
  }
  if (studiesWithSlices.length === 0) {
    return (
      <div className="dicom-empty">
        <ImageIcon size={36} />
        <strong>暂无真实 DICOM 切片</strong>
        <span>请在“上传检查”中上传单个 .dcm 或包含一组 DICOM 的 .zip 文件。</span>
      </div>
    );
  }

  return (
    <div className="dicom-viewer">
      <div className="dicom-toolbar">
        <label>
          检查序列
          <select value={studyId ?? ''} onChange={(event) => setStudyId(Number(event.target.value))}>
            {studiesWithSlices.map((study) => (
              <option key={study.id} value={study.id}>{study.study_date} · {study.series_description}</option>
            ))}
          </select>
        </label>
        {series && (
          <div className="dicom-meta">
            <span>{series.slice_count} 层</span>
            <span>{series.rows ?? '-'} × {series.columns ?? '-'}</span>
            <span>原始窗位 {series.window_center ?? '-'} / 窗宽 {series.window_width ?? '-'}</span>
            <span>显示窗位 {windowCenter.toFixed(0)} / 窗宽 {windowWidth.toFixed(0)}</span>
          </div>
        )}
      </div>

      {error && <p className="info-banner">{error}</p>}

      {currentSlice && series && (
        <div className="slice-stage">
          <button className="slice-button" onClick={() => setSliceIndex((value) => Math.max(value - 1, 0))}>
            <ChevronLeft size={20} />
          </button>
          <div className="slice-image-wrap" onClick={handleImageClick} onWheel={(event) => { event.preventDefault(); setSliceIndex((value) => clampSlice(value + (event.deltaY > 0 ? 1 : -1))); setDraft(null); }}>
            <img src={sliceImageUrl(currentSlice.id)} alt={`CT slice ${sliceIndex + 1}`} style={imageFilter()} />
            {currentAnnotations.map((annotation) => (
              <div
                className="annotation-marker saved"
                key={annotation.id}
                style={{ left: `${annotation.x_percent}%`, top: `${annotation.y_percent}%` }}
                title={`${annotation.nodule_type} · ${annotation.diameter_mm} mm`}
              >
                <span>{annotation.diameter_mm.toFixed(1)}</span>
              </div>
            ))}
            {draft && (
              <div className="annotation-marker draft" style={{ left: `${draft.x_percent}%`, top: `${draft.y_percent}%` }}>
                <span>新</span>
              </div>
            )}
            <div className="slice-overlay">
              <span>Slice {sliceIndex + 1}/{series.slice_count}</span>
              <span>Instance {currentSlice.instance_number}</span>
              <span>Location {currentSlice.slice_location ?? '-'}</span>
              <span>点击影像标记结节中心</span>
            </div>
          </div>
          <button className="slice-button" onClick={() => setSliceIndex((value) => Math.min(value + 1, series.slices.length - 1))}>
            <ChevronRight size={20} />
          </button>
        </div>
      )}

      {series && series.slices.length > 0 && (
        <div className="window-controls">
          <label>显示窗位<input type="range" min={-800} max={400} value={windowCenter} onChange={(event) => setWindowCenter(Number(event.target.value))} /></label>
          <label>显示窗宽<input type="range" min={80} max={1800} value={windowWidth} onChange={(event) => setWindowWidth(Number(event.target.value))} /></label>
        </div>
      )}

      {series && series.slices.length > 0 && (
        <input
          className="slice-slider"
          type="range"
          min={0}
          max={series.slices.length - 1}
          value={sliceIndex}
          onChange={(event) => {
            setSliceIndex(Number(event.target.value));
            setDraft(null);
          }}
        />
      )}

      <div className="annotation-panel">
        <div>
          <h3>结节标注</h3>
          <p>在 CT 图像上点击结节中心，再录入最大径和类型。</p>
        </div>
        <div className="annotation-form">
          <label>最大径 mm<input value={diameterMm} onChange={(event) => setDiameterMm(event.target.value)} /></label>
          <label>结节类型
            <select value={noduleType} onChange={(event) => setNoduleType(event.target.value)}>
              <option>磨玻璃结节</option>
              <option>混合磨玻璃结节</option>
              <option>实性结节</option>
              <option>钙化结节</option>
              <option>未分类</option>
            </select>
          </label>
          <label>归属结节
            <select value={selectedNoduleId ?? ''} disabled>
              {nodules.map((nodule) => (
                <option key={nodule.id} value={nodule.id}>{nodule.label} · {nodule.lobe}</option>
              ))}
              {nodules.length === 0 && <option value="">暂无结节</option>}
            </select>
          </label>
          <label>备注<input value={note} onChange={(event) => setNote(event.target.value)} placeholder="如右上叶尖段、毛刺、胸膜牵拉" /></label>
          <button className="primary" disabled={!draft || saving} onClick={handleSaveAnnotation}>{saving ? '保存中...' : '保存标注'}</button>
        </div>
        {measurementMessage && <p className="success-banner">{measurementMessage}</p>}
        <div className="annotation-list">
          {annotations.length === 0 && <span>当前检查暂无标注。</span>}
          {annotations.map((annotation) => (
            <div className="annotation-row" key={annotation.id}>
              <div className="annotation-main">
                <div>
                  <strong>{annotation.nodule_type} · {annotation.diameter_mm.toFixed(1)} mm</strong>
                  <span>结节 {annotation.nodule_id ?? '-'} · Slice ID {annotation.slice_id} · X {annotation.x_percent.toFixed(1)}% / Y {annotation.y_percent.toFixed(1)}% · {annotation.note || '无备注'}</span>
                </div>
                {candidateAnnotationId === annotation.id && (
                  <div className="match-candidates">
                    {matchCandidates.length === 0 && <span>暂无候选结节。</span>}
                    {matchCandidates.map((candidate) => (
                      <button key={candidate.nodule_id} onClick={() => handleConfirmCandidate(annotation.id, candidate.nodule_id)}>
                        <strong>匹配既往：{candidate.label} · {candidate.lobe}</strong>
                        <span>{candidate.nodule_type} · 匹配度 {(candidate.score * 100).toFixed(0)}%</span>
                        <small>{candidate.latest_diameter_mm ? `最近 ${candidate.latest_diameter_mm.toFixed(1)} mm · ${candidate.latest_study_date}` : '暂无既往测量'} · {candidate.reason}</small>
                      </button>
                    ))}
                    <button onClick={() => handleCreateNewNodule(annotation)}>
                      <strong>保留为新结节</strong>
                      <span>创建独立结节并生成本期测量</span>
                      <small>适用于新发结节或无法可靠匹配既往目标时。</small>
                    </button>
                  </div>
                )}
              </div>
              <div className="annotation-actions">
                <button className="small-action" onClick={() => handleShowCandidates(annotation.id)}>
                  <Link2 size={15} /> 匹配既往
                </button>
                <button className="small-action" onClick={() => handleCreateMeasurement(annotation.id)}>
                  <RefreshCw size={15} /> {annotation.nodule_id ? '更新测量' : '生成测量'}
                </button>
                <button className="icon-danger" onClick={() => handleDeleteAnnotation(annotation.id)}><Trash2 size={16} /></button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
