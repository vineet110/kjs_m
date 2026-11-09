'use client';
// Shows an uploaded file inside the page, so staff can read it without downloading (order boards PR 2).
// The bytes come from /files/{id}/view: our own API, staff only, never cached, never a storage link.
//   PDF            the browser's own PDF viewer (in a frame)
//   images         a plain <img>
//   CSV, Excel     a table drawn by React (cell text can never run as code); SheetJS reads the file
//   Word .docx     mammoth turns it into HTML, shown in a frame with scripts and links switched off
//   text           as plain text
//   anything else  "Download to open" (old .doc, zip)
// SheetJS and mammoth are big, so they load only when someone opens such a file.
import { useEffect, useState } from 'react';
import type { StoredFile } from '@/lib/api';
import { colName, previewKind, safeLinks, viewUrl } from '@/lib/preview';

const MAX_READ = 10 * 1024 * 1024; // bigger files: Download (reading them could freeze the tab)
const MAX_ROWS = 1000;
const MAX_COLS = 50;

type Sheet = { name: string; rows: string[][]; cut: boolean };
type Loaded = { sheets: Sheet[] } | { html: string } | { text: string };

export default function FilePreview({ file }: { file: StoredFile }) {
  const kind = previewKind(file);
  const [data, setData] = useState<Loaded | null>(null);
  const [err, setErr] = useState('');
  const [sheet, setSheet] = useState(0);
  const parsed = kind === 'sheet' || kind === 'word' || kind === 'text';

  useEffect(() => {
    setData(null);
    setErr('');
    setSheet(0);
    if (!parsed) return;
    if (file.size > MAX_READ) return setErr('This file is too big to show here. Download it to open it.');
    let stale = false;
    (async () => {
      const r = await fetch(viewUrl(file.id), { credentials: 'same-origin' });
      if (!r.ok) throw new Error(String(r.status));
      const buf = await r.arrayBuffer();
      if (kind === 'text') return { text: new TextDecoder().decode(buf) };
      if (kind === 'word') {
        const mammoth = await import('mammoth');
        return { html: safeLinks((await mammoth.convertToHtml({ arrayBuffer: buf })).value) };
      }
      const XLSX = await import('xlsx');
      // CSV: read as UTF-8 text first (SheetJS would read the bytes as Latin-1 and garble ₹ and Hindi), and
      // raw, so cells stay as written (no turning "1-2" into a date). dateNF: Excel's built-in "short date"
      // follows the computer's country; here it is shown the Indian way (20-Nov-2026). sheetRows: read only
      // the rows we show (+1 to know it was cut), so a huge sheet can't freeze the tab.
      const opts = { dateNF: 'dd-mmm-yyyy', sheetRows: MAX_ROWS + 1 };
      const wb = file.name.toLowerCase().endsWith('.csv')
        ? XLSX.read(new TextDecoder().decode(buf), { ...opts, type: 'string', raw: true })
        : XLSX.read(buf, { ...opts, type: 'array' });
      return {
        sheets: wb.SheetNames.map((name) => {
          const all = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets[name], { header: 1, raw: false, defval: '' });
          const cut = all.length > MAX_ROWS || all.some((r) => r.length > MAX_COLS);
          return { name, cut, rows: all.slice(0, MAX_ROWS).map((r) => r.slice(0, MAX_COLS).map((c) => String(c ?? ''))) };
        }),
      };
    })()
      .then((d) => { if (!stale) setData(d); })
      .catch(() => { if (!stale) setErr("This file couldn't be shown. Download it to open it."); });
    return () => { stale = true; };
  }, [file.id, file.name, file.size, kind, parsed]);

  if (kind === 'none') return <Fallback text="This type of file can't be shown here." />;
  if (err) return <Fallback text={err} />;
  // Phones (Android) and some browsers can't show a PDF inside a page: they would download it instead
  if (kind === 'pdf' && typeof navigator !== 'undefined' && navigator.pdfViewerEnabled === false)
    return <Fallback text="This browser can't show PDFs inside the page. Use Download to open it." />;
  if (kind === 'pdf') return <iframe src={viewUrl(file.id)} title={file.name} className="h-full min-h-[60vh] w-full rounded border bg-white" />;
  if (kind === 'image') {
    // eslint-disable-next-line @next/next/no-img-element -- a private file from our API, not a site picture
    return <img src={viewUrl(file.id)} alt={file.name} className="mx-auto max-h-full max-w-full object-contain" />;
  }
  if (!data) return <p className="p-6 text-sm text-slate-500">Opening {file.name}…</p>;
  if ('text' in data) return <pre className="h-full overflow-auto whitespace-pre-wrap break-words rounded border bg-white p-4 text-sm">{data.text}</pre>;
  if ('html' in data) {
    // sandbox="": no scripts, no forms, no new windows, and it isn't treated as our site. Links open
    // nowhere: <base target="_blank"> sends them to a new window, which the sandbox blocks.
    return <iframe sandbox="" srcDoc={wordPage(data.html)} title={file.name} className="h-full min-h-[60vh] w-full rounded border bg-white" />;
  }
  const s = data.sheets[sheet];
  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      {data.sheets.length > 1 && (
        <div role="tablist" aria-label="Sheets" className="flex flex-wrap gap-1">
          {data.sheets.map((x, i) => (
            <button key={x.name} role="tab" aria-selected={i === sheet} onClick={() => setSheet(i)}
              className={`rounded px-2 py-1 text-xs font-semibold ${i === sheet ? 'bg-ink text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}>
              {x.name}
            </button>
          ))}
        </div>
      )}
      {s.cut && <p className="text-xs text-amber-700">Showing the first {MAX_ROWS} rows and {MAX_COLS} columns. Download for the whole sheet.</p>}
      {s.rows.length === 0 ? <p className="text-sm text-slate-500">This sheet is empty.</p> : (
        <div className="min-h-0 flex-1 overflow-auto rounded border bg-white">
          <table className="border-collapse text-xs">
            <thead className="sticky top-0 bg-slate-100">
              <tr>
                <th className="border px-2 py-1 text-slate-400" />
                {Array.from({ length: Math.max(...s.rows.map((r) => r.length)) }, (_, c) => (
                  <th key={c} className="border px-2 py-1 font-semibold text-slate-500">{colName(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {s.rows.map((r, i) => (
                <tr key={i} className="odd:bg-white even:bg-slate-50">
                  <td className="border px-2 py-1 text-right text-slate-400">{i + 1}</td>
                  {r.map((c, j) => <td key={j} className="whitespace-nowrap border px-2 py-1">{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Fallback({ text }: { text: string }) {
  return <p className="rounded border border-dashed p-6 text-center text-sm text-slate-500">{text}</p>;
}

/** The Word file's HTML inside a small readable page. */
function wordPage(body: string): string {
  return `<!doctype html><html><head><meta charset="utf-8"><base target="_blank"><style>
    body{font:14px/1.6 system-ui,sans-serif;color:#111714;margin:24px;max-width:800px}
    table{border-collapse:collapse;margin:12px 0} td,th{border:1px solid #cbd5e1;padding:4px 8px;vertical-align:top}
    img{max-width:100%;height:auto} h1,h2,h3{line-height:1.25}
  </style></head><body>${body || '<p><em>This document is empty.</em></p>'}</body></html>`;
}
