import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Study } from '../lib/api';

interface Props {
  studies: Study[];
}

export default function RiskTrendChart({ studies }: Props) {
  const data = studies.map((study, index) => {
    const m = study.measurements[0];
    return {
      date: study.study_date,
      diameter: m?.diameter_mm ?? 0,
      volume: m?.volume_mm3 ?? 0,
      solid: m?.solid_component_percent ?? 0,
      index: `T${index + 1}`,
    };
  });

  return (
    <div className="chart-card">
      <h3>结节动态变化曲线</h3>
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
