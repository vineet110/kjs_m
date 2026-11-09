'use client';
// Koko: the facts it may use (it never claims anything else), and recent chat transcripts.
// Model, tone and languages: model in .env, temperature/length in config/koko.ini; it always
// replies in the visitor's language.
import { useCallback, useEffect, useState } from 'react';
import { EmptyState, fmtIST, Msg, PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure } from '@/lib/api';
import LoadError from '@/components/ui/LoadError';

type TextRow = { key: string; label: string; value: string; changed: boolean };
type Chat = { id: number; page: string; messages: { role: string; content: string }[]; suggested_enquiry: boolean; updated_at: string };

export default function KokoAdmin() {
  const [facts, setFacts] = useState<TextRow | null>(null);
  const [draft, setDraft] = useState('');
  const [chats, setChats] = useState<{ total: number; items: Chat[] } | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);

  const load = useCallback(() => {
    setLoadErr(null);
    api<TextRow[]>('/content/texts').then((rows) => {
      const f = rows.find((r) => r.key === 'koko.facts') ?? null;
      setFacts(f);
      setDraft(f?.value ?? '');
    }).catch(setLoadErr);
    api<{ total: number; items: Chat[] }>('/content/koko-chats').then(setChats).catch(setLoadErr);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function save(value: string | null) {
    try {
      await api('/content/texts/koko.facts', { method: 'PUT', body: { value } });
      setMsg({ ok: true, text: value === null ? 'Back to the original facts file.' : 'Saved. Koko uses the new facts from the next message.' });
      load();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof ApiFailure ? e.message : 'Could not save.' });
    }
  }

  return (
    <div className="space-y-8">
      <PageTitle title="Koko" sub="Koko answers only from these facts and the product catalogue. It never gives prices, lead times or capacities." />
      {loadErr != null && <LoadError error={loadErr} onRetry={load} />}
      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold">Facts</h2>
          {facts?.changed && <Pill value="pending" label="edited" />}
        </div>
        <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={18} className="input font-mono text-xs" />
        <Msg msg={msg} />
        <div className="flex gap-2">
          <button disabled={!facts || draft === facts.value} onClick={() => save(draft)} className="btn-dark">Save facts</button>
          {facts?.changed && <button onClick={() => save(null)} className="btn-ghost">Back to original</button>}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-bold">Recent chats {chats && <span className="text-sm font-normal text-slate-500">({chats.total} in total)</span>}</h2>
        {chats?.items.length === 0 && <EmptyState icon="chat" title="No chats yet" text="When visitors talk to Koko on the website, the chats show here." />}
        {chats?.items.map((c) => (
          <div key={c.id} className="card p-3 text-sm">
            <button onClick={() => setOpen(open === c.id ? null : c.id)} className="flex w-full flex-wrap items-center gap-2 text-left">
              <span className="font-medium">{c.messages.find((m) => m.role === 'user')?.content.slice(0, 80) ?? '(empty)'}</span>
              {c.suggested_enquiry && <Pill value="ok" label="buyer" />}
              <span className="ml-auto text-xs text-slate-400">{c.page} · {fmtIST(c.updated_at)} IST · {c.messages.length} messages</span>
            </button>
            {open === c.id && (
              <div className="mt-3 space-y-2">
                {c.messages.map((m, i) => (
                  <div key={i} className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 ${m.role === 'user' ? 'ml-auto bg-ink text-white' : 'bg-slate-100'}`}>{m.content}</div>
                ))}
              </div>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
