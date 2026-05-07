import type { Measurement } from '../lib/api';

interface Props {
  measurement?: Measurement;
  title: string;
}

export default function NoduleMetrics({ measurement, title }: Props) {
  if (!measurement) {
    return <div className="metric-card muted">暂无 {title} 数据</div>;
  }
  const hasRoi = measurement.min_hu != null && measurement.max_hu != null;
  return (
    <div className="metric-card">
      <span>{title}</span>
      <strong>{measurement.diameter_mm.toFixed(1)} mm</strong>
      <div className="metric-grid">
        <p>体积<br /><b>{measurement.volume_mm3.toFixed(0)} mm³</b></p>
        <p>平均 CT<br /><b>{measurement.mean_hu.toFixed(0)} HU</b></p>
        <p>实性<br /><b>{measurement.solid_component_percent.toFixed(0)}%</b></p>
        {hasRoi && <p>ROI 范围<br /><b>{measurement.min_hu?.toFixed(0)}~{measurement.max_hu?.toFixed(0)} HU</b></p>}
        {measurement.roi_area_mm2 != null && <p>ROI 面积<br /><b>{measurement.roi_area_mm2.toFixed(1)} mm²</b></p>}
      </div>
    </div>
  );
}
