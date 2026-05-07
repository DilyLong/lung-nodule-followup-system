import { ArrowLeft, CheckCircle, Copy, Download, Printer, Save } from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Page } from '../App';
import { fetchLatestReport, updateReport, type Report } from '../lib/api';

interface Props {
  patientId: number;
  setPage: (page: Page) => void;
}

function splitTableRow(line: string) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
}

function isSeparatorRow(cells: string[]) {
  return cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderMarkdown(markdown: string) {
  const lines = markdown.split('\n');
  const nodes: ReactNode[] = [];
  let index = 0;
  let key = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith('# ')) {
      nodes.push(<h1 key={key++}>{line.slice(2)}</h1>);
      index += 1;
      continue;
    }

    if (line.startsWith('## ')) {
      nodes.push(<h2 key={key++}>{line.slice(3)}</h2>);
      index += 1;
      continue;
    }

    if (line.startsWith('|')) {
      const tableLines: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        tableLines.push(lines[index].trim());
        index += 1;
      }
      const rows = tableLines.map(splitTableRow).filter((cells) => !isSeparatorRow(cells));
      const [header, ...body] = rows;
      nodes.push(
        <div className="report-table-wrapper" key={key++}>
          <table className="report-table">
            <thead>
              <tr>{header.map((cell) => <th key={cell}>{cell}</th>)}</tr>
            </thead>
            <tbody>
              {body.map((row, rowIndex) => (
                <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (line.startsWith('- ')) {
      const items: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith('- ')) {
        items.push(lines[index].trim().slice(2));
        index += 1;
      }
      nodes.push(<ul key={key++}>{items.map((item) => <li key={item}>{item}</li>)}</ul>);
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length) {
      const nextLine = lines[index].trim();
      if (!nextLine || nextLine.startsWith('# ') || nextLine.startsWith('## ') || nextLine.startsWith('|') || nextLine.startsWith('- ')) break;
      paragraph.push(nextLine);
      index += 1;
    }
    nodes.push(<p key={key++}>{paragraph.join(' ')}</p>);
  }

  return nodes;
}

function markdownToHtml(markdown: string) {
  const lines = markdown.split('\n');
  const chunks: string[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith('# ')) {
      chunks.push(`<h1>${escapeHtml(line.slice(2))}</h1>`);
      index += 1;
      continue;
    }

    if (line.startsWith('## ')) {
      chunks.push(`<h2>${escapeHtml(line.slice(3))}</h2>`);
      index += 1;
      continue;
    }

    if (line.startsWith('|')) {
      const tableLines: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        tableLines.push(lines[index].trim());
        index += 1;
      }
      const rows = tableLines.map(splitTableRow).filter((cells) => !isSeparatorRow(cells));
      const [header, ...body] = rows;
      chunks.push([
        '<table>',
        `<thead><tr>${header.map((cell) => `<th>${escapeHtml(cell)}</th>`).join('')}</tr></thead>`,
        `<tbody>${body.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')}</tbody>`,
        '</table>',
      ].join(''));
      continue;
    }

    if (line.startsWith('- ')) {
      const items: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith('- ')) {
        items.push(lines[index].trim().slice(2));
        index += 1;
      }
      chunks.push(`<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`);
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length) {
      const nextLine = lines[index].trim();
      if (!nextLine || nextLine.startsWith('# ') || nextLine.startsWith('## ') || nextLine.startsWith('|') || nextLine.startsWith('- ')) break;
      paragraph.push(nextLine);
      index += 1;
    }
    chunks.push(`<p>${escapeHtml(paragraph.join(' '))}</p>`);
  }

  return chunks.join('\n');
}

function finalMarkdown(contentMarkdown: string, doctorOpinion: string, followupPlan: string) {
  return `${contentMarkdown.trim()}\n\n## 医生编辑确认\n\n- 医生意见：${doctorOpinion.trim() || '未填写'}\n- 确认随访建议：${followupPlan.trim() || '未填写'}\n`;
}

function buildWordDocument(report: Report, contentMarkdown: string, doctorOpinion: string, followupPlan: string) {
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(report.title)}</title>
  <style>
    body { font-family: SimSun, "Microsoft YaHei", Arial, sans-serif; line-height: 1.75; color: #111827; }
    h1 { text-align: center; font-size: 22pt; margin-bottom: 24pt; }
    h2 { font-size: 15pt; border-bottom: 1px solid #d1d5db; padding-bottom: 6pt; margin-top: 20pt; }
    table { width: 100%; border-collapse: collapse; margin: 12pt 0; }
    th, td { border: 1px solid #9ca3af; padding: 6pt 8pt; text-align: left; }
    th { background: #f3f4f6; }
    ul { margin: 8pt 0 12pt 20pt; }
  </style>
</head>
<body>
${markdownToHtml(finalMarkdown(contentMarkdown, doctorOpinion, followupPlan))}
</body>
</html>`;
}

function reportFileName(report: Report) {
  return `${report.title}-${report.id}`.replace(/[\\/:*?"<>|]/g, '-');
}

function statusText(report: Report) {
  if (report.status === 'final') return `最终版${report.finalized_at ? ` · ${new Date(report.finalized_at).toLocaleString()}` : ''}`;
  return '草稿，可继续编辑';
}

export default function ReportView({ patientId, setPage }: Props) {
  const [report, setReport] = useState<Report | null>(null);
  const [contentMarkdown, setContentMarkdown] = useState('');
  const [doctorOpinion, setDoctorOpinion] = useState('');
  const [followupPlan, setFollowupPlan] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchLatestReport(patientId).then((nextReport) => {
      setReport(nextReport);
      setContentMarkdown(nextReport?.content_markdown ?? '');
      setDoctorOpinion(nextReport?.doctor_opinion ?? '');
      setFollowupPlan(nextReport?.followup_plan ?? '');
    });
  }, [patientId]);

  const previewMarkdown = useMemo(() => finalMarkdown(contentMarkdown, doctorOpinion, followupPlan), [contentMarkdown, doctorOpinion, followupPlan]);

  async function saveReport(status: 'draft' | 'final') {
    if (!report) return;
    setSaving(true);
    setMessage('');
    try {
      const updated = await updateReport(report.id, {
        content_markdown: contentMarkdown,
        doctor_opinion: doctorOpinion,
        followup_plan: followupPlan,
        status,
      });
      setReport(updated);
      setContentMarkdown(updated.content_markdown);
      setDoctorOpinion(updated.doctor_opinion);
      setFollowupPlan(updated.followup_plan);
      setMessage(status === 'final' ? '已确认最终版报告。' : '草稿已保存。');
    } finally {
      setSaving(false);
    }
  }

  async function copyReport() {
    if (report) await navigator.clipboard.writeText(previewMarkdown);
  }

  function printReport() {
    window.print();
  }

  function downloadWord() {
    if (!report) return;
    const blob = new Blob([buildWordDocument(report, contentMarkdown, doctorOpinion, followupPlan)], { type: 'application/msword;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${reportFileName(report)}.doc`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="page report-page">
      <header className="page-header report-page-header">
        <div>
          <p className="eyebrow">Structured report</p>
          <h1>结构化随访报告</h1>
          <span>可编辑报告正文、医生意见和随访建议，保存草稿或确认最终版。</span>
        </div>
        <div className="button-row report-actions">
          <button className="ghost" onClick={() => setPage({ name: 'patient', patientId })}><ArrowLeft size={17} /> 返回病例</button>
          <button className="ghost" onClick={printReport} disabled={!report}><Printer size={17} /> 打印/保存 PDF</button>
          <button className="ghost" onClick={downloadWord} disabled={!report}><Download size={17} /> 下载 Word</button>
          <button className="ghost" onClick={copyReport} disabled={!report}><Copy size={17} /> 复制 Markdown</button>
        </div>
      </header>

      {report && (
        <section className="panel report-editor report-page-header">
          <div className="report-editor-header">
            <div>
              <h2>医生编辑确认</h2>
              <span className={`model-status-chip ${report.status === 'final' ? 'real' : 'fallback'}`}>{statusText(report)}</span>
            </div>
            <div className="button-row">
              <button className="ghost" onClick={() => saveReport('draft')} disabled={saving}><Save size={17} /> 保存草稿</button>
              <button className="primary" onClick={() => saveReport('final')} disabled={saving}><CheckCircle size={17} /> 确认最终版</button>
            </div>
          </div>
          {message && <p className="success-banner compact">{message}</p>}
          <label>
            报告正文 Markdown
            <textarea value={contentMarkdown} onChange={(event) => setContentMarkdown(event.target.value)} rows={16} />
          </label>
          <div className="report-editor-grid">
            <label>
              医生意见
              <textarea value={doctorOpinion} onChange={(event) => setDoctorOpinion(event.target.value)} rows={5} placeholder="填写影像判断、临床解释或需补充的检查意见" />
            </label>
            <label>
              医生确认随访建议
              <textarea value={followupPlan} onChange={(event) => setFollowupPlan(event.target.value)} rows={5} placeholder="填写或修改复查时间、MDT/手术/穿刺建议" />
            </label>
          </div>
        </section>
      )}

      <section className="report-paper">
        {report ? <article className="report-document">{renderMarkdown(previewMarkdown)}</article> : <p className="empty">暂无报告，请先在病例详情页运行分析并生成报告。</p>}
      </section>
    </div>
  );
}
