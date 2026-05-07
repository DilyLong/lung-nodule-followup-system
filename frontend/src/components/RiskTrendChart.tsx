import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Measurement } from '../lib/api';

interface Props {
  measurements: Measurement[];
}

export default function RiskTrendChart({ measurements }: Props) {
  const data = measurements.map((measurement, index) => ({
    diameter: measurement.diameter_mm,
    volume: measurement.volume_mm3,
    solid: measurement.solid_component_percent,
    index: `T${index + 1}`,
  }));

  if (data.length === 0) {
    return <p className="empty compact">当前结节暂无动态测量曲线。</p>;
  }

  return (
    <div className="chart-card">
      <h3>目标结节动态变化曲线</h3>
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="index" />
          <YAxis />
          <Tooltip />
          <Area type="monotone" dataKey="diameter" name="最大径 mm" stroke="#2563eb" fill="#dbeafe" />
          <Area type="monotone" dataKey="solid" name="实性成分 %" stroke="#dc2626" fill="#fee2e2" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
