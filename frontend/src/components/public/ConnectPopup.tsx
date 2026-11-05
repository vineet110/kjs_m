'use client';
// "Let's connect" popup: up to 3 times per visit. The first 8 s into the visit, the second 30 s after
// the first is closed, the third 60 s after the second is closed (each wait starts when the previous
// popup is gone, so a popup left open doesn't make the next one follow straight away).
// - The WhatsApp message is drafted from the page that is open (product, category, private label...).
// - Desktop: a card in the middle; phones: a bottom sheet. The page behind is blurred.
// - Stops for the rest of the visit once someone clicks WhatsApp or asks for a quote. Never opens over
//   the enquiry form. The time of the next popup is kept in sessionStorage, so moving between pages
//   or reloading doesn't restart it.
// Switched on/off with connect_popup in config/features.ini.
import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import EnquiryButton from './EnquiryButton';
import { WhatsAppIcon } from './WhatsAppButton';
import { SITE } from '@/lib/site';

// Wait before each popup, in ms. The first counts from the start of the visit, the others from
// closing the previous popup.
const GAPS = [8_000, 30_000, 60_000];
const KEY = 'kjs-connect'; // sessionStorage: { next, shown, done }

type State = { next: number; shown: number; done: boolean }; // next: when the next popup is due (ms)


// Each popup says something a little different, so the second and third don't feel like repeats
const STEPS = [
  { eyebrow: 'Fast-track your order', title: 'Get it fast forward,', accent: "let's connect.", text: 'Skip the forms. Our sales team takes it from here on WhatsApp.', quote: false },
  { eyebrow: 'Prices, samples, MOQ', title: 'One message away', accent: 'from your quote.', text: 'Send us this message, or ask for a formal quotation.', quote: true },
  { eyebrow: 'Still exploring?', title: "We're right here", accent: 'when you are ready.', text: 'Our team replies within one working day.', quote: false },
];

function load(): State {
  try {
    const s = JSON.parse(sessionStorage.getItem(KEY) ?? 'null');
    // Only trust well-formed data (old or hand-edited values would break STEPS[shown])
    if (s && Number.isFinite(s.next) && Number.isInteger(s.shown) && s.shown >= 0 && s.shown <= GAPS.length && typeof s.done === 'boolean') return s;
  } catch {} // private mode or bad data: start fresh
  return { next: Date.now() + GAPS[0], shown: 0, done: false };
}
function save(s: State) {
  try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch {}
}

// Something the visitor is busy with that the popup must not cover: the enquiry form or the product
// quick view (both are aria-modal dialogs), or an open Koko chat (its "Close chat" button only exists
// while the chat is open)
const busy = () => !!document.querySelector('[aria-modal="true"], [aria-label="Close chat"]');

// The page's own heading (product or category name), read when the popup opens
const heading = () => document.querySelector('main h1')?.textContent?.trim() ?? '';

/** The WhatsApp message for the page that is open */
export function draftFor(path: string, name: string): string {
  const p = path.replace(/^\/en(?=\/|$)/, '') || '/';
  if (p.startsWith('/products/')) return `Hi KJS India, I'm interested in ${name || 'one of your products'}. Please share the price, MOQ and pack options.`;
  if (p.startsWith('/categories/')) return `Hi KJS India, I'm looking for ${name || 'products'} for my brand. Can you share your range and prices?`;
  if (p.startsWith('/products')) return "Hi KJS India, I'd like your product catalogue and price sheet.";
  if (p.startsWith('/private-label')) return 'Hi KJS India, I want to launch my own brand. Can we discuss private label manufacturing?';
  if (p.startsWith('/partners')) return "Hi KJS India, I'd like to partner with you as a distributor.";
  if (p.startsWith('/contact')) return 'Hi KJS India, I have an enquiry. Please get in touch.';
  return "Hi KJS India, I'd like to know more about co-manufacturing with you.";
}

export default function ConnectPopup() {
  const path = usePathname();
  const [step, setStep] = useState<number | null>(null); // the popup showing, or null
  const [hidden, setHidden] = useState(false); // true while the quote form (opened from here) is on top
  const [draft, setDraft] = useState('');
  const [typing, setTyping] = useState(true);
  const state = useRef<State | null>(null);
  const waLink = useRef<HTMLAnchorElement>(null);

  const finish = useCallback((done: boolean) => {
    const s = state.current!;
    s.done = s.done || done;
    // The next gap starts now, when this one is closed
    if (s.shown < GAPS.length) s.next = Date.now() + GAPS[s.shown];
    save(s);
    setStep(null);
    setHidden(false);
  }, []);

  // Schedule the next popup that hasn't been shown yet
  useEffect(() => {
    if (step !== null) return;
    const s = (state.current ??= load());
    save(s);
    if (s.done || s.shown >= GAPS.length) return;
    // One timer, also for the retries, so leaving the page (or unmounting) always cancels it
    let t: ReturnType<typeof setTimeout>;
    const open = () => {
      // The visitor is busy (enquiry form, quick view, Koko chat): try again a little later
      if (busy()) return void (t = setTimeout(open, 10_000));
      setDraft(draftFor(path, heading()));
      setTyping(true);
      setStep(s.shown);
      s.shown += 1;
      // Also move "next" on now: a reload while this popup is open must still wait the full gap
      // (closing it moves "next" again, from the moment it is closed)
      if (s.shown < GAPS.length) s.next = Date.now() + GAPS[s.shown];
      save(s);
    };
    t = setTimeout(open, Math.max(1_000, s.next - Date.now()));
    return () => clearTimeout(t);
  }, [step, path]);

  // While open: the "typing..." dots, Esc to close, no page scroll behind
  useEffect(() => {
    if (step === null) return;
    const t = setTimeout(() => setTyping(false), 1100);
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !hidden && finish(false);
    document.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    waLink.current?.focus();
    return () => {
      clearTimeout(t);
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
    };
  }, [step, hidden, finish]);

  if (step === null || !STEPS[step]) return null;
  const s = STEPS[step];
  const href = `${SITE.whatsapp}?text=${encodeURIComponent(draft)}`;

  return (
    <div
      className={`fixed inset-0 z-[55] flex items-end justify-center bg-ink/50 backdrop-blur-md duration-300 animate-in fade-in sm:items-center sm:p-4 ${hidden ? 'hidden' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="connect-title"
      onClick={(e) => e.target === e.currentTarget && finish(false)}
    >
      <div className="relative w-full overflow-hidden rounded-t-3xl bg-white shadow-2xl duration-500 animate-in slide-in-from-bottom-full motion-reduce:animate-none sm:max-w-md sm:rounded-3xl sm:zoom-in-90 sm:slide-in-from-bottom-8">
        {/* Phones: the grab handle of a bottom sheet */}
        <span aria-hidden="true" className="absolute left-1/2 top-2 z-10 h-1 w-10 -translate-x-1/2 rounded-full bg-white/40 sm:hidden" />

        {/* Dark top with gold rings pulsing out, and a fast-forward mark */}
        <div className="relative overflow-hidden bg-ink px-6 pb-6 pt-7 text-white">
          <span aria-hidden="true" className="absolute -right-10 -top-10 h-40 w-40 rounded-full border-[14px] border-gold/20" />
          <span aria-hidden="true" className="absolute -right-10 -top-10 h-40 w-40 animate-ping rounded-full border-2 border-gold/40 [animation-duration:2.4s] motion-reduce:hidden" />
          <button onClick={() => finish(false)} className="absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center rounded-full text-slate-300 hover:bg-white/10 hover:text-white" aria-label="Close">✕</button>
          <div className="relative flex items-center gap-2">
            <span aria-hidden="true" className="flex h-7 w-7 items-center justify-center rounded-full bg-gold text-sm font-black text-ink">»</span>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-gold">{s.eyebrow}</p>
          </div>
          <h2 id="connect-title" className="relative mt-3 text-2xl font-extrabold leading-tight">
            {s.title} <span className="text-gold">{s.accent}</span>
          </h2>
          <p className="relative mt-2 text-sm text-slate-300">{s.text}</p>
        </div>

        {/* A WhatsApp-style preview of the message we've drafted for this page */}
        <div className="bg-[#ECE5DD] px-5 py-4">
          <div className="flex items-center gap-2 text-xs text-slate-600">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#25D366] text-white"><WhatsAppIcon size={14} /></span>
            <span className="font-semibold text-slate-800">KJS India Sales</span>
          </div>
          <div className="mt-3 flex justify-end">
            {typing ? (
              <span className="flex gap-1 rounded-2xl rounded-tr-sm bg-[#DCF8C6] px-4 py-3 shadow-sm" aria-label="Drafting your message">
                {[0, 150, 300].map((d) => (
                  <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-slate-500/70" style={{ animationDelay: `${d}ms` }} />
                ))}
              </span>
            ) : (
              <p className="max-w-[85%] rounded-2xl rounded-tr-sm bg-[#DCF8C6] px-3 py-2 text-sm text-slate-800 shadow-sm duration-300 animate-in fade-in slide-in-from-bottom-2">
                {draft}
                <span className="ml-2 align-bottom text-[10px] text-slate-500">✓✓</span>
              </p>
            )}
          </div>
        </div>

        <div className="px-6 pb-6 pt-5">
          <a
            ref={waLink}
            href={href}
            target="_blank"
            rel="noopener"
            onClick={() => finish(true)}
            className="group flex w-full items-center justify-center gap-2 rounded-xl bg-[#25D366] px-4 py-3.5 text-base font-bold text-white shadow-lg shadow-[#25D366]/30 transition hover:bg-[#1EBE5A] motion-safe:hover:-translate-y-0.5"
          >
            <WhatsAppIcon size={22} />
            Chat on WhatsApp
            <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">→</span>
          </a>
          {s.quote && (
            <EnquiryButton
              label="Request a formal quote"
              source="quote"
              title="Request a quote"
              className="btn-ghost mt-2 w-full !py-3"
              onOpen={() => setHidden(true)}
              onClose={() => finish(true)}
            />
          )}
          <button onClick={() => finish(false)} className="mt-3 w-full text-center text-xs text-slate-500 hover:text-slate-800">
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
