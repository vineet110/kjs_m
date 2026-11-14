'use client';
// "Report a problem" in the portal header: a bug, issue or suggestion for the developers.
// The page it is sent from and the date and time are added by themselves (the time by the server).
// Saved in the database for now; admins read them on /admin/complaints.
import { useEffect, useRef, useState } from 'react';
import { api, ApiFailure } from '@/lib/api';
import Spinner from '@/components/ui/Spinner';
import { uploadOne } from './FileList';
import { Icon } from './icons';
import { useToast } from './Toast';

const MIN_TITLE = 3; // words, the same rule as the server
const MIN_DESCRIPTION = 15;
const words = (s: string) => s.trim().split(/\s+/).filter(Boolean).length;

export default function ReportProblem() {
  const toast = useToast();
  const ref = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState('bug');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [shot, setShot] = useState<File | null>(null);
  const [path, setPath] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  function start() {
    setPath(window.location.pathname); // the page they are on now, without ?search parts
    setKind('bug');
    setTitle('');
    setDescription('');
    setShot(null);
    setErr('');
    setOpen(true);
  }

  const titleWords = words(title);
  const descWords = words(description);
  const ready = titleWords >= MIN_TITLE && descWords >= MIN_DESCRIPTION;

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setErr('');
    let saved: { id: number } | null = null;
    try {
      saved = await api<{ id: number }>('/complaints', { method: 'POST', body: { kind, title, description, page_path: path.slice(0, 300) } });
      if (shot) await uploadOne('complaint', String(saved.id), shot);
      toast('Thanks! Your report was sent to the developers.');
      setOpen(false);
    } catch (x) {
      const why = x instanceof ApiFailure ? x.message : 'Something went wrong.';
      if (saved) {
        // The report is saved; only the screenshot failed. Don't let them send it twice.
        toast(`Your report was sent, but the screenshot was not: ${why}`, 'error');
        setOpen(false);
      } else {
        setErr(why);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" onClick={start} aria-label="Report a problem" title="Report a problem"
        className="flex h-8 items-center gap-1 rounded px-2 text-xs text-slate-600 hover:bg-stone-100">
        <Icon name="info" className="h-4 w-4" />
        <span className="hidden sm:inline">Report a problem</span>
      </button>
      <dialog
        ref={ref}
        aria-labelledby="report-title"
        onCancel={(e) => {
          e.preventDefault(); // Escape: stay open while sending
          if (!busy) setOpen(false);
        }}
        onClose={() => {
          if (busy) ref.current?.showModal(); // closed by force while sending: keep showing it
          else setOpen(false);
        }}
        className="w-[calc(100vw-2rem)] max-w-lg rounded-2xl p-0 shadow-2xl backdrop:bg-black/40"
      >
        <form onSubmit={send} className="space-y-3 p-6">
          <h2 id="report-title" className="text-lg font-bold">Report a problem</h2>
          <p className="text-xs text-slate-500">From page <span className="font-mono">{path}</span>. The date and time are added automatically.</p>

          <div>
            <label htmlFor="rp-kind" className="label">Type</label>
            <select id="rp-kind" className="input" value={kind} onChange={(e) => setKind(e.target.value)} disabled={busy}>
              <option value="bug">Bug (something is broken)</option>
              <option value="issue">Issue (something is hard or wrong)</option>
              <option value="suggestion">Suggestion (an idea)</option>
            </select>
          </div>

          <div>
            <label htmlFor="rp-title" className="label">Title (at least {MIN_TITLE} words)</label>
            <input id="rp-title" className="input" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} disabled={busy}
              placeholder="Import button does nothing" />
            <p className={`mt-1 text-xs ${titleWords >= MIN_TITLE ? 'text-emerald-700' : 'text-slate-500'}`}>{titleWords} / {MIN_TITLE} words</p>
          </div>

          <div>
            <label htmlFor="rp-desc" className="label">Description (at least {MIN_DESCRIPTION} words)</label>
            <textarea id="rp-desc" className="input min-h-28" value={description} maxLength={5000} onChange={(e) => setDescription(e.target.value)} disabled={busy}
              placeholder="What did you do, what did you expect, and what happened instead?" />
            <p className={`mt-1 text-xs ${descWords >= MIN_DESCRIPTION ? 'text-emerald-700' : 'text-slate-500'}`}>{descWords} / {MIN_DESCRIPTION} words</p>
          </div>

          <div>
            <label htmlFor="rp-shot" className="label">Screenshot (optional)</label>
            <input id="rp-shot" type="file" accept=".png,.jpg,.jpeg,.webp" disabled={busy}
              onChange={(e) => setShot(e.target.files?.[0] ?? null)} className="text-sm" />
          </div>

          {err && <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">{err}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={() => setOpen(false)} disabled={busy} className="btn-ghost">Cancel</button>
            <button type="submit" disabled={!ready || busy} aria-busy={busy} className="btn-dark">
              {busy && <Spinner />}
              {busy ? 'Sending…' : 'Send'}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
