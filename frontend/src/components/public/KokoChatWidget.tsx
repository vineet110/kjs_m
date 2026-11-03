'use client';
// Koko: answers from KJS facts only (backend decides). When the visitor looks like a buyer,
// we show a small contact form; the chat goes with it and becomes a lead with a summary.
import { useEffect, useRef, useState } from 'react';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure } from '@/lib/api';
import { SITE } from '@/lib/site';

type Msg = { role: 'user' | 'assistant'; content: string };

const HELLO: Msg = {
  role: 'assistant',
  content: 'Hi! I am Koko. Ask me about our stick packs, blending, packaging or private label. I reply in your language.',
};

export default function KokoChatWidget() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([HELLO]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [sent, setSent] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  // Random id for this conversation (no personal data), so staff can read the transcript in Admin > Koko.
  const chatId = useRef(`c-${Math.random().toString(36).slice(2, 12)}-${Date.now().toString(36)}`);

  // Braces matter: an effect may only return a cleanup function. Newer Chrome makes
  // scrollIntoView() return a Promise, which React then tries to call -> "destroy is not a function".
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [msgs, showForm]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    const next = [...msgs, { role: 'user' as const, content: text }];
    setMsgs(next);
    setInput('');
    setBusy(true);
    try {
      // Don't send our greeting; the server only needs the real conversation.
      const res = await api<{ reply: string; suggest_enquiry: boolean }>('/koko/chat', {
        method: 'POST',
        body: { messages: next.slice(1), page: window.location.pathname, chat_id: chatId.current },
      });
      setMsgs([...next, { role: 'assistant', content: res.reply }]);
      if (res.suggest_enquiry && !sent) setShowForm(true);
    } catch (err) {
      const msg = err instanceof ApiFailure ? err.message : 'Sorry, I could not reply.';
      setMsgs([...next, { role: 'assistant', content: `${msg} You can also WhatsApp ${SITE.phone}.` }]);
    } finally {
      setBusy(false);
    }
  }

  async function sendLead(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const email = String(f.get('email') || '').trim();
    try {
      await api('/public/leads', {
        method: 'POST',
        body: {
          source: 'koko', name: f.get('name'), email: email || null, phone: f.get('phone'),
          company: f.get('company'), consent: f.get('consent') === 'on',
          chat: msgs.slice(1), source_page: window.location.pathname,
        },
      });
      setSent(true);
      setShowForm(false);
      setMsgs((m) => [...m, { role: 'assistant', content: 'Thank you! I have sent a summary to our sales team. They will contact you soon.' }]);
    } catch (err) {
      alert(err instanceof ApiFailure ? err.message : 'Could not send. Please try WhatsApp.');
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-50">
      {open ? (
        <div className="flex h-[520px] w-[calc(100vw-2.5rem)] max-w-sm flex-col overflow-hidden rounded-2xl border bg-white shadow-2xl">
          <div className="flex items-center justify-between bg-forest p-4 text-white">
            <div>
              <p className="text-sm font-bold">Koko · KJS assistant</p>
              <p className="text-xs text-emerald-200">Answers from KJS information only</p>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close chat" className="text-white/80 hover:text-white">✕</button>
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto p-3 text-sm">
            {msgs.map((m, i) => (
              <div key={i} className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 ${m.role === 'user' ? 'ml-auto bg-forest text-white' : 'bg-slate-100 text-slate-800'}`}>
                {m.content}
              </div>
            ))}
            {busy && <div className="w-16 rounded-xl bg-slate-100 px-3 py-2 text-slate-500">…</div>}
            {showForm && (
              <form onSubmit={sendLead} className="space-y-2 rounded-xl border border-gold/50 bg-gold/5 p-3">
                <p className="text-xs font-semibold">Share your details and our sales team will send a quote:</p>
                <input name="name" required minLength={2} placeholder="Name *" className="input" />
                <input name="company" placeholder="Company" className="input" />
                <input name="email" type="email" placeholder="Email" className="input" />
                <PhoneInput id="koko-phone" />
                <label className="flex items-start gap-2 text-[11px] text-slate-600">
                  <input type="checkbox" name="consent" required className="mt-0.5" />
                  I agree to be contacted about this request (DPDP Act 2023).
                </label>
                <div className="flex gap-2">
                  <button className="btn-gold flex-1">Send</button>
                  <button type="button" onClick={() => setShowForm(false)} className="btn-ghost">Later</button>
                </div>
              </form>
            )}
            <div ref={endRef} />
          </div>
          <form onSubmit={send} className="flex gap-2 border-t bg-slate-50 p-3">
            <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000} placeholder="Ask about our products…" className="input" />
            <button disabled={busy} className="btn-dark">Send</button>
          </form>
        </div>
      ) : (
        <button onClick={() => setOpen(true)} className="btn-gold rounded-full px-5 py-3 shadow-lg">
          💬 Ask Koko
        </button>
      )}
    </div>
  );
}
