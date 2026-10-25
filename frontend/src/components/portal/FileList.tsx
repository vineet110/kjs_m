'use client';
// Files of one owner (an order board, a product): upload, download, ask to delete.
// Deleting needs an approver (files.approve), so staff can't lose documents by accident.
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiFailure, upload, type StoredFile } from '@/lib/api';
import { fmtIST, Pill } from './ui';

function size(n: number) {
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
}

export default function FileList({ ownerType, ownerId, canUpload = true, publicToggle = false }: {
  ownerType: string; ownerId: string; canUpload?: boolean; publicToggle?: boolean;
}) {
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const [isPublic, setIsPublic] = useState(publicToggle);

  const load = useCallback(() => {
    api<StoredFile[]>(`/files?owner_type=${ownerType}&owner_id=${encodeURIComponent(ownerId)}`).then(setFiles).catch(() => setFiles([]));
  }, [ownerType, ownerId]);
  useEffect(() => {
    load();
  }, [load]);

  async function send(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setErr('');
    const form = new FormData();
    form.set('owner_type', ownerType);
    form.set('owner_id', ownerId);
    form.set('is_public', String(isPublic));
    form.set('file', file);
    try {
      await upload('/files', form);
      load();
    } catch (x) {
      setErr(x instanceof ApiFailure ? x.message : 'Upload failed.');
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
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

  return (
    <div className="space-y-2">
      {canUpload && (
        <div className="flex flex-wrap items-center gap-3">
          <label className={`btn-ghost cursor-pointer py-1 ${busy ? 'opacity-50' : ''}`}>
            {busy ? 'Uploading…' : 'Upload file'}
            <input ref={input} type="file" className="hidden" onChange={send} disabled={busy} />
          </label>
          {publicToggle && (
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} /> Show on website</label>
          )}
        </div>
      )}
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="divide-y rounded-lg border">
        {files.length === 0 && <p className="p-3 text-sm text-slate-500">No files yet.</p>}
        {files.map((f) => (
          <div key={f.id} className="flex flex-wrap items-center gap-2 p-2 text-sm">
            <a href={`/api/v1/files/${f.id}/download`} className="font-medium underline">{f.name}</a>
            <span className="text-xs text-slate-500">{size(f.size)} · {f.uploaded_by_name} · {fmtIST(f.created_at)}</span>
            {f.is_public && <Pill value="ok" label="on website" />}
            <span className="ml-auto">
              {f.delete_status === 'requested'
                ? <Pill value="pending" label="delete requested" />
                : <button onClick={() => askDelete(f)} className="text-xs text-red-700 underline">Request delete</button>}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
