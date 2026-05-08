import axios from 'axios';

export function errorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail?.message) return detail.message;
    if (!error.response) return '后端服务未连接，请确认 FastAPI 已在 8000 端口启动。';
  }
  return fallback;
}

export const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
});

export interface Measurement {
  id: number;
  nodule_id: number;
  study_id: number;
  diameter_mm: number;
  volume_mm3: number;
  mean_hu: number;
  min_hu?: number | null;
  max_hu?: number | null;
  roi_area_mm2?: number | null;
  solid_component_percent: number;
  spiculation_score: number;
  lobulation_score: number;
  pleural_retraction_score: number;
  thumbnail_seed: number;
}

export interface ImageSlice {
  id: number;
  study_id: number;
  instance_number: number;
  slice_location: number | null;
  image_path: string;
  dicom_path: string | null;
  rows: number;
  columns: number;
  window_center: number;
  window_width: number;
}

export interface StudyImageSeries {
  study_id: number;
  patient_id: number;
  study_date: string;
  series_description: string;
  slice_count: number;
  rows: number | null;
  columns: number | null;
  window_center: number | null;
  window_width: number | null;
  slices: ImageSlice[];
}

export interface NoduleAnnotation {
  id: number;
  patient_id: number;
  study_id: number;
  slice_id: number;
  nodule_id: number | null;
  x_percent: number;
  y_percent: number;
  diameter_mm: number;
  nodule_type: string;
  note: string;
  created_at: string;
}

export interface NoduleAnnotationCreate {
  patient_id: number;
  study_id: number;
  slice_id: number;
  nodule_id?: number | null;
  x_percent: number;
  y_percent: number;
  diameter_mm: number;
  nodule_type: string;
  note: string;
}

export interface Study {
  id: number;
  patient_id: number;
  study_date: string;
  modality: string;
  scanner: string;
  slice_thickness_mm: number;
  series_description: string;
  file_name: string | null;
  status: string;
  measurements: Measurement[];
  slices: ImageSlice[];
}

export interface NoduleCreate {
  label: string;
  lobe: string;
  nodule_type: string;
  baseline_impression: string;
}

export interface Nodule {
  id: number;
  patient_id: number;
  label: string;
  lobe: string;
  nodule_type: string;
  baseline_impression: string;
  measurements: Measurement[];
}

export interface Analysis {
  id: number;
  patient_id: number;
  nodule_id: number | null;
  created_at: string;
  risk_score: number;
  risk_level: string;
  registration_quality: number;
  volume_doubling_time_days: number | null;
  diameter_change_mm: number;
  volume_change_percent: number;
  density_change_hu: number;
  recommendation: string;
  features_json: string;
}

export interface PatientSummary {
  id: number;
  patient_code: string;
  name: string;
  sex: string;
  age: number;
  smoking_history: string;
  primary_diagnosis: string;
  nodule_type: string | null;
  latest_study_date: string | null;
  latest_risk_level: string | null;
  latest_risk_score: number | null;
}

export interface PatientDetail {
  id: number;
  patient_code: string;
  name: string;
  sex: string;
  age: number;
  smoking_history: string;
  family_history: string;
  primary_diagnosis: string;
  studies: Study[];
  nodules: Nodule[];
  analyses: Analysis[];
}

export interface Report {
  id: number;
  patient_id: number;
  analysis_id: number;
  created_at: string;
  title: string;
  content_markdown: string;
  doctor_opinion: string;
  followup_plan: string;
  status: 'draft' | 'final' | string;
  finalized_at: string | null;
}

export interface ReportVersion {
  id: number;
  report_id: number;
  version_number: number;
  created_at: string;
  status: string;
  content_markdown: string;
  doctor_opinion: string;
  followup_plan: string;
  operator: string;
}

export interface ReportAuditLog {
  id: number;
  report_id: number;
  created_at: string;
  event: string;
  message: string;
  operator: string;
}

function operatorParam(operator?: string) {
  return operator ? `?operator=${encodeURIComponent(operator)}` : '';
}

export async function fetchReportVersions(reportId: number) {
  const { data } = await api.get<ReportVersion[]>(`/reports/${reportId}/versions`);
  return data;
}

export async function fetchReportAudit(reportId: number) {
  const { data } = await api.get<ReportAuditLog[]>(`/reports/${reportId}/audit`);
  return data;
}

export async function createReportRevision(reportId: number, operator?: string) {
  const { data } = await api.post<Report>(`/reports/${reportId}/revisions${operatorParam(operator)}`);
  return data;
}

export interface ReportUpdatePayload {
  content_markdown: string;
  doctor_opinion: string;
  followup_plan: string;
  status: 'draft' | 'final';
}

export async function fetchPatients() {
  const { data } = await api.get<PatientSummary[]>('/patients');
  return data;
}

export async function fetchPatient(id: number) {
  const { data } = await api.get<PatientDetail>(`/patients/${id}`);
  return data;
}

export async function runAnalysis(patientId: number, noduleId?: number | null) {
  const suffix = noduleId ? `?nodule_id=${noduleId}` : '';
  const { data } = await api.post<Analysis>(`/analysis/${patientId}/run${suffix}`);
  return data;
}

export async function createReport(analysisId: number, operator?: string) {
  const { data } = await api.post<Report>(`/reports/${analysisId}${operatorParam(operator)}`);
  return data;
}

export function reportDocUrl(reportId: number) {
  return `${api.defaults.baseURL}/reports/${reportId}/export.doc`;
}

export function reportPrintUrl(reportId: number) {
  return `${api.defaults.baseURL}/reports/${reportId}/print.html`;
}

export async function updateReport(reportId: number, payload: ReportUpdatePayload, operator?: string) {
  const { data } = await api.put<Report>(`/reports/${reportId}${operatorParam(operator)}`, payload);
  return data;
}

export async function fetchLatestReport(patientId: number) {
  const { data } = await api.get<Report | null>(`/reports/patient/${patientId}/latest`);
  return data;
}

export async function fetchStudyImageSeries(studyId: number) {
  const { data } = await api.get<StudyImageSeries>(`/imaging/studies/${studyId}`);
  return data;
}

export async function fetchStudyAnnotations(studyId: number) {
  const { data } = await api.get<NoduleAnnotation[]>(`/annotations/studies/${studyId}`);
  return data;
}

export async function createNoduleAnnotation(payload: NoduleAnnotationCreate) {
  const { data } = await api.post<NoduleAnnotation>('/annotations', payload);
  return data;
}

export async function updateNoduleAnnotation(annotationId: number, payload: NoduleAnnotationCreate) {
  const { data } = await api.put<NoduleAnnotation>(`/annotations/${annotationId}`, payload);
  return data;
}

export async function deleteNoduleAnnotation(annotationId: number) {
  await api.delete(`/annotations/${annotationId}`);
}

export interface FollowupPoint {
  study_id: number;
  study_date: string;
  diameter_mm: number;
  volume_mm3: number;
  mean_hu: number;
  min_hu?: number | null;
  max_hu?: number | null;
  roi_area_mm2?: number | null;
  solid_component_percent: number;
  source: string;
}

export interface FollowupComparison {
  patient_id: number;
  nodule_id: number | null;
  nodule_type: string | null;
  point_count: number;
  baseline_date: string | null;
  latest_date: string | null;
  diameter_change_mm: number | null;
  volume_change_percent: number | null;
  annualized_diameter_growth_mm: number | null;
  points: FollowupPoint[];
}

export interface AnnotationMeasurementResult {
  annotation: NoduleAnnotation;
  measurement: Measurement;
  nodule: Nodule;
  message: string;
}

export async function createMeasurementFromAnnotation(annotationId: number) {
  const { data } = await api.post<AnnotationMeasurementResult>(`/annotations/${annotationId}/measurement`);
  return data;
}

export async function fetchPatientFollowup(patientId: number, noduleId?: number | null) {
  const suffix = noduleId ? `?nodule_id=${noduleId}` : '';
  const { data } = await api.get<FollowupComparison>(`/followup/patients/${patientId}${suffix}`);
  return data;
}

export async function createPatientNodule(patientId: number, payload: NoduleCreate) {
  const { data } = await api.post<Nodule>(`/patients/${patientId}/nodules`, payload);
  return data;
}

export interface MatchCandidate {
  nodule_id: number;
  label: string;
  lobe: string;
  nodule_type: string;
  latest_diameter_mm: number | null;
  latest_study_date: string | null;
  score: number;
  reason: string;
}

export async function fetchMatchCandidates(annotationId: number) {
  const { data } = await api.get<MatchCandidate[]>(`/matching/annotations/${annotationId}/candidates`);
  return data;
}

export async function confirmAnnotationMatch(annotationId: number, noduleId: number) {
  const { data } = await api.post<NoduleAnnotation>(`/matching/annotations/${annotationId}/confirm?nodule_id=${noduleId}`);
  return data;
}

export interface ImportSpec {
  spec_version: string;
  date_format: string;
  coordinate_system: Record<string, string>;
  dicom_layout: Record<string, string>;
  files: Record<string, { required_columns: string[]; optional_columns: string[]; notes: string }>;
  allowed_values: Record<string, string[]>;
  quality_checks: string[];
  future_import_endpoint: { planned: boolean; scope: string };
}

export interface ImportValidationIssue {
  file: string;
  row: number | null;
  column: string | null;
  severity: 'error' | 'warning' | string;
  message: string;
}

export interface ImportFileValidationSummary {
  file: string;
  row_count: number;
  missing_required_columns: string[];
  unknown_columns: string[];
}

export interface ImportValidationReport {
  valid: boolean;
  summary: {
    file_count: number;
    total_rows: number;
    error_count: number;
    warning_count: number;
  };
  files: ImportFileValidationSummary[];
  issues: ImportValidationIssue[];
}

export interface ImportCommitCounts {
  patients_created: number;
  patients_updated: number;
  studies_created: number;
  studies_updated: number;
  nodules_created: number;
  nodules_updated: number;
  measurements_created: number;
  measurements_updated: number;
}

export interface ImportBatch {
  id: number;
  created_at: string;
  committed_at: string | null;
  rolled_back_at: string | null;
  status: string;
  qc_score: number;
  counts_json: string;
  issues_json: string;
  message: string;
  operator: string;
}

export interface ImportBatchEntity {
  id: number;
  batch_id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  stable_key: string;
  previous_json: string | null;
  operator: string;
}

export interface ImportBatchDetail {
  batch: ImportBatch;
  entities: ImportBatchEntity[];
}

export interface ImportCommitReport {
  committed: boolean;
  validation: ImportValidationReport;
  counts: ImportCommitCounts;
  patient_ids: number[];
  message: string;
  batch: ImportBatch | null;
}

export interface ImportPreviewReport {
  validation: ImportValidationReport;
  counts: ImportCommitCounts;
  qc_score: number;
  qc_issues: ImportValidationIssue[];
  message: string;
}

function buildDownloadUrl(path: string, patientId?: number | null) {
  const baseUrl = api.defaults.baseURL ?? '';
  const suffix = patientId ? `?patient_id=${patientId}` : '';
  return `${baseUrl}${path}${suffix}`;
}

export function researchPackageZipUrl(patientId?: number | null) {
  return buildDownloadUrl('/exports/research-package.zip', patientId);
}

export function cohortTableCsvUrl(patientId?: number | null) {
  return buildDownloadUrl('/exports/cohort-table.csv', patientId);
}

export function researchTableCsvUrl(patientId?: number | null) {
  return buildDownloadUrl('/exports/research-table.csv', patientId);
}

export function measurementsCsvUrl(patientId?: number | null) {
  return buildDownloadUrl('/exports/measurements.csv', patientId);
}

export async function fetchImportSpec() {
  const { data } = await api.get<ImportSpec>('/imports/spec');
  return data;
}

export async function validateDatasetImport(formData: FormData) {
  const { data } = await api.post<ImportValidationReport>('/imports/validate', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
  return data;
}

export async function previewDatasetImport(formData: FormData) {
  const { data } = await api.post<ImportPreviewReport>('/imports/preview', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
  return data;
}

export async function commitDatasetImport(formData: FormData, operator?: string) {
  const { data } = await api.post<ImportCommitReport>(`/imports/commit${operatorParam(operator)}`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
  return data;
}

export async function fetchImportBatches() {
  const { data } = await api.get<ImportBatch[]>('/imports/batches');
  return data;
}

export async function fetchImportBatchDetail(batchId: number) {
  const { data } = await api.get<ImportBatchDetail>(`/imports/batches/${batchId}`);
  return data;
}

export async function rollbackImportBatch(batchId: number, operator?: string) {
  const { data } = await api.post<ImportBatch>(`/imports/batches/${batchId}/rollback${operatorParam(operator)}`);
  return data;
}

export interface ModelArtifactStatus {
  name: string;
  path: string;
  format: string;
  exists: boolean;
  dependency: string;
  dependency_available: boolean;
  sha256?: string | null;
  status: string;
}

export interface ModelRuntimeStatus {
  artifact_dir: string;
  input_schema_version: string;
  surrogate_model_version: string;
  active_mode: string;
  active_backend: string;
  artifacts: ModelArtifactStatus[];
  dependencies: Record<string, boolean>;
  fallback_model: {
    name: string;
    backend: string;
    status: string;
  };
}

export async function fetchModelRuntimeStatus() {
  const { data } = await api.get<ModelRuntimeStatus>('/model/status');
  return data;
}

export interface DemoWalkthroughStep {
  order: number;
  page: string;
  action: string;
  expected: string;
}

export interface DemoRepresentativeStory {
  patient_id: number | null;
  patient_code: string;
  name: string;
  label: string;
  headline: string;
  demo_reason: string;
  nodule_count: number;
  latest_report_id: number | null;
  latest_report_status: string | null;
  latest_analysis_id: number | null;
  latest_risk_level: string | null;
  latest_risk_score: number | null;
}

export interface DemoStatus {
  synthetic_patient_count: number;
  analysis_count: number;
  report_count: number;
  trained: boolean;
  training_report_exists: boolean;
  latest_report_id: number | null;
  latest_report_status: string | null;
  latest_analysis_id: number | null;
  latest_analysis_risk_level: string | null;
  representative_ready_count: number;
  representative_total_count: number;
  representative_stories: DemoRepresentativeStory[];
}

export interface DemoSafetyNotice {
  title: string;
  items: string[];
}

export interface DemoWalkthrough {
  title: string;
  summary: string;
  readiness: ModelTrainingReadiness;
  status: DemoStatus;
  safety_notice: DemoSafetyNotice;
  steps: DemoWalkthroughStep[];
}

export interface DemoResetResult {
  reset: boolean;
  message: string;
  cleared: Record<string, number>;
  seeded: Record<string, unknown>;
}

export interface DemoPrepareResult {
  prepared: boolean;
  seeded: Record<string, unknown>;
  training: ModelTrainingReport;
  created: Array<{ patient_id: number; patient_code: string; nodule_id: number; analysis_id: number; report_id: number; risk_level: string; risk_score: number; story: { label: string; headline: string; demo_reason: string } }>;
}

export async function fetchDemoWalkthrough() {
  const { data } = await api.get<DemoWalkthrough>('/demo/walkthrough');
  return data;
}

export async function fetchDemoRepresentativeCases() {
  const { data } = await api.get<DemoRepresentativeStory[]>('/demo/representative-cases');
  return data;
}

export async function resetDemoState() {
  const { data } = await api.post<DemoResetResult>('/demo/reset');
  return data;
}

export async function prepareDemoState() {
  const { data } = await api.post<DemoPrepareResult>('/demo/prepare');
  return data;
}
export interface ModelSelfCheckIssue {
  field: string;
  severity: 'error' | 'warning' | string;
  message: string;
}

export interface ModelSelfCheckCheck {
  name: string;
  passed: boolean;
  message: string;
}

export interface ModelSelfCheckReport {
  passed: boolean;
  mode: string;
  backend: string;
  demo_input_source: string;
  checks: ModelSelfCheckCheck[];
  issues: ModelSelfCheckIssue[];
  model_input_preview: {
    input_schema_version?: string;
    timepoint_count?: number;
    time_series?: Record<string, unknown>[];
    clinical_features?: Record<string, unknown>;
    derived_features?: Record<string, unknown>;
  };
  inference: null | {
    risk_score?: number;
    risk_level?: string;
    model_name?: string;
    model_status?: string;
    model_version?: string;
    input_schema_version?: string;
    backend?: string;
    fallback_reason?: string;
    model_artifact?: string;
    model_artifact_hash?: string | null;
    model_input_feature_count?: number;
    inference_started_at?: string;
    contributions?: Array<Record<string, unknown>>;
  };
  runtime_status: ModelRuntimeStatus;
}

export async function runModelSelfCheck() {
  const { data } = await api.post<ModelSelfCheckReport>('/model/self-check');
  return data;
}

export interface DemoTrainingCohortResult {
  loaded: boolean;
  message: string;
  synthetic: boolean;
  case_count: number;
  patients_created: number;
  studies_created: number;
  nodules_created: number;
  measurements_created: number;
  before: Record<string, number>;
  after: Record<string, number>;
}

export async function loadDemoTrainingCohort() {
  const { data } = await api.post<DemoTrainingCohortResult>('/model/training/demo-cohort');
  return data;
}

export interface ModelTrainingReadiness {
  ready: boolean;
  eligible_sample_count: number;
  positive_count: number;
  negative_count: number;
  excluded_count: number;
  exclusions: Array<Record<string, unknown>>;
  artifact_path: string;
  artifact_exists: boolean;
  training_report_path: string;
  training_report_exists: boolean;
  latest_report: null | Record<string, unknown>;
}

export interface ModelTrainingReport {
  trained: boolean;
  message: string;
  operator: string;
  eligible_sample_count: number;
  positive_count: number;
  negative_count: number;
  excluded_count: number;
  exclusions: Array<Record<string, unknown>>;
  generated_at?: string | null;
  model_version?: string | null;
  artifact_path?: string | null;
  training_report_path?: string | null;
  train_sample_count?: number | null;
  validation_sample_count?: number | null;
  metrics?: Record<string, number> | null;
  calibration_bins: Array<Record<string, unknown>>;
  thresholds?: Record<string, number> | null;
  feature_names: string[];
  samples: Array<Record<string, unknown>>;
}

export async function fetchModelTrainingReadiness() {
  const { data } = await api.get<ModelTrainingReadiness>('/model/training/readiness');
  return data;
}

export async function runModelTraining(operator?: string) {
  const { data } = await api.post<ModelTrainingReport>(`/model/training/run${operatorParam(operator)}`);
  return data;
}
export interface SystemStatus {
  backend: {
    status: string;
    api_version: string;
    checked_at: string;
  };
  database: {
    patient_count: number;
    study_count: number;
    nodule_count: number;
    measurement_count: number;
    analysis_count: number;
    report_count: number;
    final_report_count: number;
    import_batch_count: number;
    measurement_sources: Record<string, number>;
  };
  data_quality: {
    label_distribution: Record<string, number>;
    pathology_distribution: Record<string, number>;
    missing_fields: Record<string, number>;
    followup_interval_days: { count: number; min: number | null; median: number | null; max: number | null };
    training_readiness: {
      ready: boolean;
      eligible_sample_count: number;
      positive_count: number;
      negative_count: number;
      excluded_count: number;
      top_exclusions: Array<Record<string, unknown>>;
    };
  };
  model: {
    active_mode: string;
    active_backend: string;
    input_schema_version: string;
    surrogate_model_version: string;
    artifacts: ModelArtifactStatus[];
  };
  exports: Array<{ name: string; endpoint: string; available: boolean }>;
  latest: {
    analysis: null | { id: number; patient_id: number; nodule_id: number | null; created_at: string; risk_level: string; risk_score: number };
    report: null | { id: number; patient_id: number; analysis_id: number; created_at: string; status: string; finalized_at: string | null };
    final_report: null | { id: number; patient_id: number; analysis_id: number; created_at: string; status: string; finalized_at: string | null };
    import_batch: null | { id: number; created_at: string; status: string; qc_score: number; message: string };
  };
  readiness: Array<{ key: string; label: string; available: boolean }>;
  actions: Array<{ key: string; severity: 'info' | 'warning' | string; title: string; description: string; target_page: 'upload' | 'dashboard' | 'modelStatus' | string }>;
}

export async function fetchSystemStatus() {
  const { data } = await api.get<SystemStatus>('/system/status');
  return data;
}

export function sliceImageUrl(sliceId: number) {
  return `${api.defaults.baseURL}/imaging/slices/${sliceId}/image`;
}

export function registrationPreviewUrl(path: string) {
  return `${api.defaults.baseURL}/imaging/registration/${path}`;
}
