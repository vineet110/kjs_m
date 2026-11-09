'use client';
// Koko: answers from KJS facts only (backend decides). When the visitor looks like a buyer,
// we show a small contact form; the chat goes with it and becomes a lead with a summary.
// On a product or category page, the first reply also shows that category's products as cards
// (they come from our database, not the AI, so they are always right).
import Image from 'next/image';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { useEffect, useRef, useState } from 'react';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure, type KokoCatalogue, type KokoReply } from '@/lib/api';
import { imageOf } from '@/lib/catalogue';
import { SITE } from '@/lib/site';

// card: shown under that reply only; never sent back to the server (the AI gets the words, not the card)
type Msg = { role: 'user' | 'assistant'; content: string; card?: KokoCatalogue };

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
  const t = useTranslations('koko');
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
      const res = await api<KokoReply>('/koko/chat', {
        method: 'POST',
        body: { messages: next.slice(1).map(({ role, content }) => ({ role, content })), page: window.location.pathname, chat_id: chatId.current },
        timeoutMs: 35_000, // the server may wait up to 25 s for the AI, so more than the usual 20 s
        safeToRepeat: true, // asking again only gives another reply
      });
      setMsgs([...next, { role: 'assistant', content: res.reply, card: res.catalogue ?? undefined }]);
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
          chat: msgs.slice(1).map(({ role, content }) => ({ role, content })), source_page: window.location.pathname,
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
          <div className="flex items-center justify-between border-b-2 border-gold bg-ink p-4 text-white">
            <div>
              <p className="text-sm font-bold">Koko · KJS assistant</p>
              <p className="text-xs text-gold-light/80">Answers from KJS information only</p>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close chat" className="text-white/80 hover:text-white">✕</button>
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto p-3 text-sm">
            {msgs.map((m, i) => (
              <div key={i} className="space-y-2">
                <div className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 ${m.role === 'user' ? 'ml-auto bg-ink text-white' : 'bg-slate-100 text-slate-800'}`}>
                  {m.content}
                </div>
                {m.card && <CatalogueCard card={m.card} title={t('cardTitle', { category: m.card.category_name })} seeAll={t('seeAll', { category: m.card.category_name })} />}
              </div>
            ))}
            {busy && <div className="w-16 rounded-xl bg-slate-100 px-3 py-2 text-slate-500">…</div>}
            {showForm && (
              <form onSubmit={sendLead} className="space-y-2 rounded-xl border border-gold/50 bg-gold/5 p-3">
                <p className="text-xs font-semibold">Share your details and our sales team will send a quote:</p>
                <input name="name" required minLength={2} placeholder="Name *" className="input" />
                <input name="company" placeholder="Company" className="input" />
                <input name="email" type="email" placeholder="Email" className="input" />
                <PhoneInput id="koko-phone" placeholder="Phone / WhatsApp *" />
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

/** Up to 6 products of the page's category, two per row, each a link to its product page. */
function CatalogueCard({ card, title, seeAll }: { card: KokoCatalogue; title: string; seeAll: string }) {
  return (
    <section aria-label={title} className="rounded-xl border border-slate-200 bg-white p-2">
      <p className="px-1 pb-2 text-xs font-semibold text-slate-600">{title}</p>
      <ul className="grid grid-cols-2 gap-2">
        {card.products.map((p) => {
          const image = imageOf(p); // a bad image_path shows the category name instead
          return (
            <li key={p.slug}>
              <Link href={`/products/${p.slug}`} className="group block overflow-hidden rounded-lg border border-slate-100 hover:border-gold">
                <div className="relative flex h-16 items-center justify-center bg-slate-100">
                  {image
                    ? <Image src={image} alt="" fill className="object-cover" sizes="120px" />
                    : <span className="px-1 text-center text-[10px] text-slate-400">{card.category_name}</span>}
                </div>
                <p className="line-clamp-2 px-2 py-1 text-[11px] font-medium leading-tight group-hover:text-forest">{p.name}</p>
              </Link>
            </li>
          );
        })}
      </ul>
      <Link href={`/categories/${card.category_slug}`} className="mt-2 block px-1 text-xs font-semibold text-gold-dark underline">
        {seeAll} →
      </Link>
    </section>
  );
}
