import { useEffect, useState } from 'react';
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fetchPatientFollowup, type FollowupComparison as FollowupComparisonType } from '../lib/api';

interface Props {
  patientId: number;
  noduleId: number | null;
  refreshKey: number;
}

function formatOptional(value: number | null | undefined, digits = 0, suffix = '') {
  return value == null ? '-' : `${value.toFixed(digits)}${suffix}`;
}

function formatHuRange(minHu: number | null | undefined, maxHu: number | null | undefined) {
  return minHu == null || maxHu == null ? '-' : `${minHu.toFixed(0)}~${maxHu.toFixed(0)} HU`;
}

export default function FollowupComparison({ patientId, noduleId, refreshKey }: Props) {
  const [followup, setFollowup] = useState<FollowupComparisonType | null>(null);

  useEffect(() => {
    fetchPatientFollowup(patientId, noduleId).then(setFollowup);
  }, [patientId, noduleId, refreshKey]);

  if (!followup) {
    return <p className="empty">正在加载随访测量...</p>;
  }

  if (followup.points.length === 0) {
    return <p className="empty">暂无随访测量。请先在 DICOM 切片上保存标注，并点击“生成测量”。</p>;
  }

  const chartData = followup.points.map((point, index) => ({
    ...point,
    label: `T${index + 1}`,
    volume_ml: Number((point.volume_mm3 / 1000).toFixed(2)),
  }));

  return (
    <div className="followup-comparison">
      <div className="followup-summary">
        <div><span>结节类型</span><strong>{followup.nodule_type ?? '未分类'}</strong></div>
        <div><span>测量次数</span><strong>{followup.point_count}</strong></div>
        <div><span>最大径变化</span><strong>{followup.diameter_change_mm ?? '-'} mm</strong></div>
        <div><span>年增长率</span><strong>{followup.annualized_diameter_growth_mm ?? '-'} mm/年</strong></div>
      </div>

      <div className="chart-card followup-chart">
        <h3>真实随访测量趋势</h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="diameter_mm" name="最大径 mm" stroke="#2563eb" strokeWidth={3} />
            <Line type="monotone" dataKey="volume_ml" name="估算体积 ml" stroke="#dc2626" strokeWidth={3} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <table className="followup-table">
        <thead>
          <tr>
            <th>检查日期</th>
            <th>最大径</th>
            <th>估算体积</th>
            <th>平均 CT 值</th>
            <th>ROI 范围</th>
            <th>ROI 面积</th>
            <th>实性成分</th>
            <th>来源</th>
          </tr>
        </thead>
        <tbody>
          {followup.points.map((point) => (
            <tr key={point.study_id}>
              <td>{point.study_date}</td>
              <td>{point.diameter_mm.toFixed(1)} mm</td>
              <td>{point.volume_mm3.toFixed(1)} mm³</td>
              <td>{point.mean_hu.toFixed(0)} HU</td>
              <td>{formatHuRange(point.min_hu, point.max_hu)}</td>
              <td>{formatOptional(point.roi_area_mm2, 1, ' mm²')}</td>
              <td>{point.solid_component_percent.toFixed(0)}%</td>
              <td>{point.source === 'annotation' ? 'DICOM 标注' : '演示数据'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
