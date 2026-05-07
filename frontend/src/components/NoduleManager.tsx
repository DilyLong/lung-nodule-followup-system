import { PlusCircle } from 'lucide-react';
import { useState } from 'react';
import { createPatientNodule, type Nodule, type NoduleCreate } from '../lib/api';

interface Props {
  patientId: number;
  nodules: Nodule[];
  selectedNoduleId: number | null;
  onSelect: (noduleId: number) => void;
  onCreated: (nodule: Nodule) => void;
}

const defaultForm: NoduleCreate = {
  label: '',
  lobe: '右上叶',
  nodule_type: '磨玻璃结节',
  baseline_impression: '',
};

export default function NoduleManager({ patientId, nodules, selectedNoduleId, onSelect, onCreated }: Props) {
  const [form, setForm] = useState<NoduleCreate>(defaultForm);
  const [saving, setSaving] = useState(false);

  async function handleCreate() {
    if (!form.label.trim()) return;
    setSaving(true);
    try {
      const nodule = await createPatientNodule(patientId, form);
      onCreated(nodule);
      onSelect(nodule.id);
      setForm(defaultForm);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="nodule-manager">
      <div className="nodule-list">
        {nodules.map((nodule) => (
          <button
            key={nodule.id}
            className={nodule.id === selectedNoduleId ? 'nodule-card active' : 'nodule-card'}
            onClick={() => onSelect(nodule.id)}
          >
            <strong>{nodule.label}</strong>
            <span>{nodule.lobe} · {nodule.nodule_type}</span>
            <small>{nodule.baseline_impression}</small>
          </button>
        ))}
        {nodules.length === 0 && <p className="empty compact">暂无结节，请先新建一个结节。</p>}
      </div>
      <div className="nodule-create">
        <h3>新建结节</h3>
        <div className="nodule-form">
          <label>编号/名称<input value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} placeholder="如 N1 / 主结节" /></label>
          <label>肺叶
            <select value={form.lobe} onChange={(event) => setForm({ ...form, lobe: event.target.value })}>
              <option>右上叶</option>
              <option>右中叶</option>
              <option>右下叶</option>
              <option>左上叶</option>
              <option>左下叶</option>
              <option>待确认</option>
            </select>
          </label>
          <label>类型
            <select value={form.nodule_type} onChange={(event) => setForm({ ...form, nodule_type: event.target.value })}>
              <option>磨玻璃结节</option>
              <option>混合磨玻璃结节</option>
              <option>实性结节</option>
              <option>钙化结节</option>
              <option>未分类</option>
            </select>
          </label>
          <label>描述<input value={form.baseline_impression} onChange={(event) => setForm({ ...form, baseline_impression: event.target.value })} placeholder="如右上叶尖段，边界清" /></label>
          <button className="primary" disabled={saving || !form.label.trim()} onClick={handleCreate}><PlusCircle size={16} /> 新建</button>
        </div>
      </div>
    </div>
  );
}
