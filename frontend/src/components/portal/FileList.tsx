'use client';
// Files of one owner (an order board, a product): upload, preview, download, ask to delete.
// Deleting needs an approver (files.approve, or e.g. the board's owner), so staff can't lose documents by accident.
// Preview: click a file to see it beside the list (half the width on a computer, below it on a phone),
// or full screen (Esc closes). Download is always there too.
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiFailure, upload, type StoredFile } from '@/lib/api';
import { downloadUrl } from '@/lib/preview';
import FilePreview from './FilePreview';
import LoadError from '@/components/ui/LoadError';
import { fmtIST, Pill } from './ui';

function size(n: number) {
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
}

/** Uploads files to one owner, one by one. Returns a message for each file that failed (empty = all saved). */
export async function uploadFiles(ownerType: string, ownerId: string, files: File[], isPublic = false): Promise<string[]> {
  const failed: string[] = [];
  for (const file of files) {
    const form = new FormData();
    form.set('owner_type', ownerType);
    form.set('owner_id', ownerId);
    form.set('is_public', String(isPublic));
    form.set('file', file);
    try {
      await upload('/files', form);
    } catch (x) {
      failed.push(`${file.name}: ${x instanceof ApiFailure ? x.message : 'Upload failed.'}`);
    }
  }
  return failed;
}

export default function FileList({ ownerType, ownerId, canUpload = true, publicToggle = false, canDecide = false }: {
  ownerType: string; ownerId: string; canUpload?: boolean; publicToggle?: boolean;
  canDecide?: boolean; // may approve / reject delete requests here (e.g. an order board's owner)
}) {
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const [isPublic, setIsPublic] = useState(publicToggle);
  const [openId, setOpenId] = useState<number | null>(null);
  const [full, setFull] = useState(false);
  const open = files.find((f) => f.id === openId) ?? null; // a deleted file closes by itself
  const isFull = full && !!open; // and leaves full screen with it
  const panel = useRef<HTMLElement>(null);

  // Full screen uses the browser's own full screen where it can, because then Esc works even after a
  // click inside the PDF or Word frame (a key pressed in a frame never reaches this page). Elsewhere
  // (iPhone) the panel just covers the page. Either way the page behind doesn't scroll.
  useEffect(() => {
    if (!isFull) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setFull(false);
    const onExit = () => { if (!document.fullscreenElement) setFull(false); };
    document.addEventListener('keydown', onKey);
    document.addEventListener('fullscreenchange', onExit);
    const before = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('fullscreenchange', onExit);
      document.body.style.overflow = before;
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    };
  }, [isFull]);
  function toggleFull() {
    if (isFull) return setFull(false);
    setFull(true);
    panel.current?.requestFullscreen?.().catch(() => {}); // not allowed (iPhone): the covering panel is used
  }

  const [loadErr, setLoadErr] = useState<unknown>(null);
  const load = useCallback(() => {
    setLoadErr(null);
    api<StoredFile[]>(`/files?owner_type=${ownerType}&owner_id=${encodeURIComponent(ownerId)}`).then(setFiles).catch(setLoadErr);
  }, [ownerType, ownerId]);
  useEffect(() => {
    load();
  }, [load]);

  async function send(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []);
    if (!picked.length) return;
    setBusy(true);
    setErr('');
    // One at a time, so one bad file (too big, wrong type) doesn't stop the others
    const failed = await uploadFiles(ownerType, ownerId, picked, isPublic);
    setErr(failed.join(' '));
    setBusy(false);
    if (input.current) input.current.value = '';
    load();
  }

  async function askDelete(f: StoredFile) {
    const reason = prompt(`Why should "${f.name}" be deleted? An approver will check.`);
    if (!reason || reason.trim().length < 3) return;
    try {
      await api(`/files/${f.id}/delete-request`, { method: 'POST', body: { reason } });
      load();
    } catch (x) {
      setErr(x instanceof ApiFailure ? x.message : 'Could not send.');
    }
  }

  async function decide(f: StoredFile, approve: boolean) {
    if (approve && !confirm(`Delete "${f.name}"? The file is removed for good.`)) return;
    setErr('');
    try {
      await api(`/files/${f.id}/delete-decision`, { method: 'POST', body: { approve } });
      load();
    } catch (x) {
      setErr(x instanceof ApiFailure ? x.message : 'Could not save.');
    }
  }

  return (
    <div className="space-y-2">
      {canUpload && (
        <div className="flex flex-wrap items-center gap-3">
          <label className={`btn-ghost cursor-pointer py-1 ${busy ? 'opacity-50' : ''}`}>
            {busy ? 'Uploading…' : 'Upload files'}
            <input ref={input} type="file" multiple className="hidden" onChange={send} disabled={busy} />
          </label>
          {publicToggle && (
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} /> Show on website</label>
          )}
        </div>
      )}
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className={open && !full ? 'grid gap-3 lg:grid-cols-2' : ''}>
      <div className="h-fit divide-y rounded-lg border bg-white">
        {loadErr ? <LoadError error={loadErr} onRetry={load} className="m-3" />
          : files.length === 0 && <p className="p-3 text-sm text-slate-500">No files yet.</p>}
        {files.map((f) => (
          <div key={f.id} className={`flex flex-wrap items-center gap-2 p-2 text-sm ${f.id === openId ? 'bg-gold/10' : ''}`}>
            <button onClick={() => { setOpenId(f.id === openId ? null : f.id); setFull(false); }} aria-pressed={f.id === openId}
              className="text-left font-medium underline">
              {f.name}
            </button>
            <span className="text-xs text-slate-500">{size(f.size)} · {f.uploaded_by_name} · {fmtIST(f.created_at)}</span>
            {f.is_public && <Pill value="ok" label="on website" />}
            <span className="ml-auto flex items-center gap-2">
              <a href={downloadUrl(f.id)} className="text-xs underline">Download</a>
              {f.delete_status === 'requested'
                ? <Pill value="pending" label="delete requested" />
                : <button onClick={() => askDelete(f)} className="text-xs text-red-700 underline">Request delete</button>}
              {f.delete_status === 'requested' && canDecide && f.own_request && (
                <span className="text-xs text-slate-500">You asked: someone else decides</span>
              )}
              {f.delete_status === 'requested' && canDecide && !f.own_request && (
                <>
                  <button onClick={() => decide(f, true)} className="text-xs font-semibold text-red-700 underline">Approve delete</button>
                  <button onClick={() => decide(f, false)} className="text-xs underline">Keep file</button>
                </>
              )}
            </span>
            {f.delete_status === 'requested' && f.delete_reason && (
              <p className="w-full text-xs text-slate-500">Reason: {f.delete_reason}</p>
            )}
          </div>
        ))}
      </div>
      {open && (
        <section ref={panel} aria-label={`Preview of ${open.name}`}
          className={isFull ? 'fixed inset-0 z-50 flex flex-col gap-3 bg-paper p-4' : 'flex h-[75vh] flex-col gap-2 rounded-lg border bg-paper p-3 lg:sticky lg:top-16'}>
          <div className="flex flex-wrap items-center gap-2">
            {/* Phones: the name gets its own line (beside three buttons it was cut to "po-11…"); wider: one row */}
            <p className="min-w-0 basis-full truncate text-sm font-semibold sm:basis-auto sm:flex-1" title={open.name}>{open.name}</p>
            <button onClick={toggleFull} className="btn-ghost py-1 text-xs">{isFull ? 'Exit full screen' : 'Full screen'}</button>
            <a href={downloadUrl(open.id)} className="btn-ghost py-1 text-xs">Download</a>
            <button onClick={() => { setOpenId(null); setFull(false); }} className="btn-ghost py-1 text-xs" aria-label="Close preview">Close</button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto"><FilePreview key={open.id} file={open} /></div>
        </section>
      )}
      </div>
    </div>
  );
}
