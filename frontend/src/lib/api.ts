import axios from 'axios';

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
}

export async function fetchPatients() {
  const { data } = await api.get<PatientSummary[]>('/patients');
  return data;
}

export async function fetchPatient(id: number) {
  const { data } = await api.get<PatientDetail>(`/patients/${id}`);
  return data;
}

export async function runAnalysis(patientId: number) {
  const { data } = await api.post<Analysis>(`/analysis/${patientId}/run`);
  return data;
}

export async function createReport(analysisId: number) {
  const { data } = await api.post<Report>(`/reports/${analysisId}`);
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

function buildDownloadUrl(path: string, patientId?: number | null) {
  const baseUrl = api.defaults.baseURL ?? '';
  const suffix = patientId ? `?patient_id=${patientId}` : '';
  return `${baseUrl}${path}${suffix}`;
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

export interface ModelArtifactStatus {
  name: string;
  path: string;
  format: string;
  exists: boolean;
  dependency: string;
  dependency_available: boolean;
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

export function sliceImageUrl(sliceId: number) {
  return `${api.defaults.baseURL}/imaging/slices/${sliceId}/image`;
}

export function registrationPreviewUrl(path: string) {
  return `${api.defaults.baseURL}/imaging/registration/${path}`;
}
