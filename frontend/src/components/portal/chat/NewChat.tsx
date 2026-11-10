'use client';
// "+" on the chat page: start a direct message, a group chat (2 or more other people) or a channel.
// The people picker uses GET /employee/colleagues (active staff).
import { useEffect, useRef, useState } from 'react';
import { api, type Colleague } from '@/lib/api';
import type { ChatChannel } from '@/lib/chat';
import { errorText } from '@/components/ui/LoadError';

type Mode = 'dm' | 'group' | 'channel';
const TABS: { mode: Mode; label: string }[] = [
  { mode: 'dm', label: 'Direct message' },
  { mode: 'group', label: 'Group chat' },
  { mode: 'channel', label: 'Channel' },
];

export default function NewChat({ meId, onDone, onClose }: {
  meId: number; onDone: (c: ChatChannel) => void; onClose: () => void;
}) {
  const [mode, setMode] = useState<Mode>('dm');
  const [people, setPeople] = useState<Colleague[] | null>(null);
  const [find, setFind] = useState('');
  const [picked, setPicked] = useState<number[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const first = useRef<HTMLInputElement>(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    api<Colleague[]>('/employee/colleagues')
      .then((all) => setPeople(all.filter((p) => p.id !== meId)))
      .catch((e) => setErr(errorText(e, 'Could not load colleagues.')));
    first.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && close.current();
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
    // Only when the dialog opens (or the account changes): live events redraw the page many times, and
    // this used to reload the colleagues and pull the focus back to the search box each time (PR #55 review)
  }, [meId]);

  const shown = (people ?? []).filter((p) => p.name.toLowerCase().includes(find.trim().toLowerCase()));
  const toggle = (id: number) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  async function run(call: () => Promise<ChatChannel>) {
    setBusy(true);
    setErr('');
    try {
      onDone(await call());
    } catch (e) {
      setErr(errorText(e, 'Could not create the chat.'));
      setBusy(false);
    }
  }
  const openDm = (id: number) => run(() => api<ChatChannel>(`/chat/dm/${id}`, { method: 'POST' }));
  const create = (e: React.FormEvent) => {
    e.preventDefault();
    run(() => api<ChatChannel>('/chat/channels', {
      method: 'POST',
      body: { kind: mode, name, description: mode === 'channel' ? description : '', is_private: isPrivate, member_ids: picked },
    }));
  };
  const canCreate = mode === 'group' ? picked.length >= 2 : name.trim().length >= 2;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 p-4 pt-16" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label="New chat" className="flex max-h-[80dvh] w-full max-w-md flex-col overflow-hidden rounded-xl bg-white shadow-xl">
        <div className="flex border-b text-sm" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.mode} type="button" role="tab" aria-selected={mode === t.mode}
              onClick={() => { setMode(t.mode); setPicked([]); setErr(''); }}
              className={`flex-1 px-3 py-2 ${mode === t.mode ? 'border-b-2 border-gold font-semibold' : 'text-slate-500 hover:bg-stone-50'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <form onSubmit={create} className="flex min-h-0 flex-1 flex-col gap-2 p-3">
          {mode === 'channel' && (
            <>
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Channel name, e.g. sales" className="input" required />
              <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} placeholder="What is it for? (optional)" className="input" />
              <label className="flex items-center gap-2 text-xs text-slate-600">
                <input type="checkbox" checked={isPrivate} onChange={(e) => setIsPrivate(e.target.checked)} /> Private
              </label>
            </>
          )}
          {mode === 'group' && (
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Group name (optional)" className="input" />
          )}
          <input ref={first} value={find} onChange={(e) => setFind(e.target.value)} placeholder="Find a colleague" className="input" aria-label="Find a colleague" />
          <p className="text-xs text-slate-500">
            {mode === 'dm' ? 'Pick one person.' : mode === 'group' ? `Pick at least 2 people (${picked.length} picked).` : `Add people now or later (${picked.length} picked).`}
          </p>
          <ul className="min-h-[120px] flex-1 overflow-y-auto rounded border">
            {people === null && !err && <li className="p-3 text-sm text-slate-400">Loading…</li>}
            {people !== null && shown.length === 0 && <li className="p-3 text-sm text-slate-400">Nobody found.</li>}
            {shown.map((p) => (
              <li key={p.id}>
                {mode === 'dm' ? (
                  <button type="button" disabled={busy} onClick={() => openDm(p.id)} className="w-full px-3 py-2 text-left text-sm hover:bg-stone-50">
                    {p.name}
                  </button>
                ) : (
                  <label className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-stone-50">
                    <input type="checkbox" checked={picked.includes(p.id)} onChange={() => toggle(p.id)} /> {p.name}
                  </label>
                )}
              </li>
            ))}
          </ul>
          {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
            {mode !== 'dm' && (
              <button type="submit" disabled={busy || !canCreate} className="btn-gold">
                {busy ? 'Creating…' : mode === 'group' ? 'Start group chat' : 'Create channel'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
