import { ArrowLeft, Copy, Download, Printer } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import type { Page } from '../App';
import { fetchLatestReport, type Report } from '../lib/api';

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

function buildWordDocument(report: Report) {
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
${markdownToHtml(report.content_markdown)}
</body>
</html>`;
}

function reportFileName(report: Report) {
  return `${report.title}-${report.id}`.replace(/[\\/:*?"<>|]/g, '-');
}

export default function ReportView({ patientId, setPage }: Props) {
  const [report, setReport] = useState<Report | null>(null);

  useEffect(() => {
    fetchLatestReport(patientId).then(setReport);
  }, [patientId]);

  async function copyReport() {
    if (report) await navigator.clipboard.writeText(report.content_markdown);
  }

  function printReport() {
    window.print();
  }

  function downloadWord() {
    if (!report) return;
    const blob = new Blob([buildWordDocument(report)], { type: 'application/msword;charset=utf-8' });
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
          <span>可复制 Markdown，也可直接打印保存 PDF 或下载 Word 兼容文档。</span>
        </div>
        <div className="button-row report-actions">
          <button className="ghost" onClick={() => setPage({ name: 'patient', patientId })}><ArrowLeft size={17} /> 返回病例</button>
          <button className="ghost" onClick={printReport} disabled={!report}><Printer size={17} /> 打印/保存 PDF</button>
          <button className="ghost" onClick={downloadWord} disabled={!report}><Download size={17} /> 下载 Word</button>
          <button className="primary" onClick={copyReport} disabled={!report}><Copy size={17} /> 复制 Markdown</button>
        </div>
      </header>

      <section className="report-paper">
        {report ? <article className="report-document">{renderMarkdown(report.content_markdown)}</article> : <p className="empty">暂无报告，请先在病例详情页运行分析并生成报告。</p>}
      </section>
    </div>
  );
}
