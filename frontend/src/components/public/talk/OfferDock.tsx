'use client';
// "Get your offer" (site_ui.ini offer_box): a small yellow box on the left edge.
// - Pop-ups come out of it at popup_times seconds after the page opens (5, 8, 11 ... then the same pattern
//   again), settle below it, newest on top, older ones fading out slowly. They are true activity lines from
//   Admin > Website > Pop-up activity, with "2 hours ago" worked out from the real time.
// - Hovering a pop-up or the box (tapping, on phones) opens a small form: phone number, plus name and a note if
//   they like. It is sent as a lead (source website_offer) with consent. Only one pop-up stays below it.
// - An untouched form warns ("about to slip away…") and folds back into the box; never while someone is in it,
//   and what they typed is kept.
// - Stops after popups_per_visit, or once the form is sent. Pauses under a popup window or the Koko chat.
import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiFailure, type ActivityLine, type SiteUi } from '@/lib/api';
import { phoneOk, popupAt, relTime } from '@/lib/talk';
import { once, somethingOpen, useTalkPage } from './useTalkPage';

type Props = { texts: Record<string, string>; ui: SiteUi };
type Pop = { id: number; text: string; when: string; leaving: boolean };
const COUNT_KEY = 'kjs-talk-pops'; // sessionStorage: pop-ups shown this visit

function shownThisVisit(): number {
  try { return Number(sessionStorage.getItem(COUNT_KEY)) || 0; } catch { return 0; }
}

export default function OfferDock({ texts, ui }: Props) {
  const here = useTalkPage(!!ui.talk_all_pages);
  const on = ui.enabled && ui.offer_box === true && here; // an older API without the switch: no box
  const path = usePathname() || '/';
  const t = (k: string) => texts[`offer.${k}`] ?? '';

  const [lines, setLines] = useState<ActivityLine[]>([]);
  const [pops, setPops] = useState<Pop[]>([]);
  const [open, setOpen] = useState(false);
  const [warn, setWarn] = useState(false);
  const [folding, setFolding] = useState(false);
  const [sent, setSent] = useState(false);
  const [done, setDone] = useState(false);
  const [bump, setBump] = useState(0);
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [note, setNote] = useState('');
  const [extra, setExtra] = useState(false);
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const honeypot = useRef<HTMLInputElement>(null);
  const hoverFeed = useRef(false);
  const hoverForm = useRef(false);
  const next = useRef(0);
  const ids = useRef(0);
  const closeTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const openRef = useRef(false); // the form is open (read inside timers)
  const boxRef = useRef<HTMLButtonElement>(null);
  openRef.current = open;

  const phoneScreen = () => !window.matchMedia('(hover: hover)').matches || window.innerWidth < 700;
  const calm = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Each pop-up (and each fold) makes the box give a little bump. Animated in place, never re-created, so a
  // keyboard user's focus on the box stays where it is.
  useEffect(() => {
    if (!bump || calm()) return;
    boxRef.current?.animate?.([{ transform: 'none' }, { transform: 'translateX(5px) scale(1.08)' }, { transform: 'none' }], { duration: 500 });
  }, [bump]);

  // Real activity lines (none: the box still shows, without pop-ups). Loaded after the page, never blocking it.
  useEffect(() => {
    if (!on) return;
    setSent(once.done('offer-sent'));
    api<ActivityLine[]>('/public/activity').then(setLines).catch(() => setLines([]));
  }, [on]);

  const fadeOut = useCallback((id: number) => {
    setPops((ps) => ps.map((p) => (p.id === id ? { ...p, leaving: true } : p)));
    setTimeout(() => setPops((ps) => ps.filter((p) => p.id !== id)), calm() ? 0 : ui.popup_fade_ms ?? 1800);
  }, [ui.popup_fade_ms]);

  // Pop-ups on their own clock (from page load), whether the form is open or not
  useEffect(() => {
    if (!on || sent || !lines.length) return;
    const start = performance.now();
    const times = ui.popup_times ?? [5, 8, 11, 15, 17, 25];
    let n = 0;
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      const due = popupAt(times, n++) * 1000 - (performance.now() - start);
      timer = setTimeout(fire, Math.max(0, due));
    };
    const fire = () => {
      if (shownThisVisit() >= (ui.popups_per_visit ?? 20)) return; // done for this visit
      if (!document.hidden && !somethingOpen() && !hoverFeed.current) {
        const line = lines[next.current++ % lines.length];
        const id = ++ids.current;
        try { sessionStorage.setItem(COUNT_KEY, String(shownThisVisit() + 1)); } catch { /* private window */ }
        setBump((b) => b + 1);
        setPops((ps) => {
          const max = openRef.current || phoneScreen() ? (ui.popups_on_screen_phone ?? 1) : (ui.popups_on_screen ?? 3);
          const live = ps.filter((p) => !p.leaving);
          live.slice(max - 1).forEach((p) => setTimeout(() => fadeOut(p.id), 0));
          return [{ id, text: line.text, when: relTime(line.happened_at), leaving: false }, ...ps];
        });
        const stay = () => setTimeout(() => (hoverFeed.current ? stay() : fadeOut(id)), (ui.popup_show_seconds ?? 4) * 1000);
        stay();
      }
      schedule();
    };
    schedule();
    return () => clearTimeout(timer);
  }, [on, sent, lines, ui.popup_times, ui.popups_per_visit, ui.popups_on_screen, ui.popups_on_screen_phone, ui.popup_show_seconds, fadeOut]);

  // ---------- The form ----------
  const disarm = () => { closeTimers.current.forEach(clearTimeout); closeTimers.current = []; setWarn(false); };
  /** Folds the form back into the box. withWarning: only when it closes by itself, never on ✕ or a click away. */
  const fold = useCallback((withWarning = false) => {
    disarm();
    setWarn(withWarning);
    setFolding(true);
    hoverForm.current = false; // the form goes away under the mouse: no "leave" event will come
    setTimeout(() => { setOpen(false); setFolding(false); setWarn(false); setTerms(false); setBump((b) => b + 1); }, calm() ? 0 : 900);
  }, []);
  const arm = useCallback(() => {
    disarm();
    const busy = hoverForm.current || (formRef.current?.contains(document.activeElement) ?? false);
    if (busy) return; // never closes while someone is in it
    const total = (ui.form_open_seconds ?? 14) * 1000;
    const warnAt = total - (ui.form_warn_seconds ?? 4) * 1000;
    closeTimers.current = [setTimeout(() => setWarn(true), warnAt), setTimeout(() => fold(true), total)];
  }, [ui.form_open_seconds, ui.form_warn_seconds, fold]);
  const openForm = () => {
    if (open || somethingOpen()) return;
    setDone(false);
    setError('');
    setOpen(true);
    // Only the newest pop-up stays, below the form
    setPops((ps) => { ps.filter((p) => !p.leaving).slice(1).forEach((p) => setTimeout(() => fadeOut(p.id), 0)); return ps; });
  };
  useEffect(() => { if (open && !done) arm(); return disarm; }, [open, done, arm]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!phoneOk(phone)) return setError('Please enter a phone number with 6 to 15 digits.');
    setSending(true);
    setError('');
    try {
      await api('/public/leads', {
        method: 'POST',
        body: {
          source: 'website_offer', name: name.trim(), phone: phone.trim(), message: note.trim(), consent: true,
          website: honeypot.current?.value ?? '', source_page: path,
        },
      });
      once.mark('offer-sent');
      setSent(true);
      setDone(true);
      setPhone(''); setName(''); setNote(''); setExtra(false);
      pops.forEach((p) => fadeOut(p.id));
      disarm();
      setTimeout(() => fold(), 3000);
    } catch (err) {
      setError(err instanceof ApiFailure ? err.message : 'Could not send. Please try WhatsApp instead.');
    } finally {
      setSending(false);
    }
  }

  // Click outside the form, the box or the pop-ups: fold it away
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      const dock = document.getElementById('offer-dock');
      if (dock && !dock.contains(e.target as Node)) fold();
    };
    document.addEventListener('pointerdown', away);
    return () => document.removeEventListener('pointerdown', away);
  }, [open, fold]);

  if (!on) return null;
  const hoverOpen = (e: React.PointerEvent) => { if (e.pointerType === 'mouse') openForm(); };
  // Form open: the pop-ups move down, below it
  const feedTop = open ? 'calc(50% + 110px)' : 'calc(100% + 10px)';

  return (
    <div id="offer-dock" className="fixed left-0 top-[38%] z-[45] -translate-y-1/2">
      <button
        ref={boxRef}
        type="button"
        onClick={openForm}
        onPointerEnter={hoverOpen}
        aria-expanded={open}
        aria-controls="offer-form"
        className={`flex flex-col items-center gap-2 rounded-r-xl px-2 py-3 text-xs font-extrabold tracking-wide shadow-lg motion-safe:animate-in motion-safe:zoom-in-95 ${sent ? 'bg-[#25D366] text-[#06210F]' : 'bg-gold text-ink'}`}
      >
        <span aria-hidden="true" className="h-2 w-2 rounded-full bg-[#25D366] ring-2 ring-[#25D366]/30" />
        <span className="[writing-mode:vertical-rl] rotate-180">{sent ? 'We will call you' : t('box')}</span>
      </button>

      {/* Pop-ups, newest on top, below the box */}
      <div
        className="absolute left-0 flex w-max flex-col gap-2 transition-[top] duration-300"
        style={{ top: feedTop }}
        onPointerEnter={(e) => { hoverFeed.current = true; hoverOpen(e); }}
        onPointerLeave={() => { hoverFeed.current = false; }}
      >
        {pops.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={openForm}
            className={`flex max-w-[min(290px,calc(100vw-24px))] items-center gap-2.5 rounded-r-xl border border-l-4 border-slate-200 border-l-gold bg-white px-3 py-2 text-left text-[13px] leading-snug text-slate-800 shadow-lg max-sm:max-w-[220px] max-sm:text-xs motion-safe:origin-top-left motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-50 motion-safe:slide-in-from-top-6 motion-safe:duration-500 ${p.leaving ? 'opacity-0 transition-opacity' : ''}`}
            style={p.leaving ? { transitionDuration: `${ui.popup_fade_ms ?? 1800}ms` } : undefined}
          >
            <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full bg-[#25D366]" />
            <span>
              {p.text}
              <span className="block text-[11px] text-slate-500">
                {p.when} · <span className="font-bold text-gold-dark">{window.matchMedia('(hover: hover)').matches ? 'Hover' : 'Tap'} for your offer</span>
              </span>
            </span>
          </button>
        ))}
      </div>

      {open && (
        <form method="post"
          id="offer-form"
          ref={formRef}
          onSubmit={submit}
          noValidate
          onPointerEnter={() => { hoverForm.current = true; disarm(); }}
          onPointerLeave={() => { hoverForm.current = false; arm(); }}
          onFocus={disarm}
          onBlur={() => setTimeout(() => { if (!formRef.current?.contains(document.activeElement)) arm(); }, 0)}
          className={`absolute left-[calc(100%+6px)] top-1/2 w-[min(290px,calc(100vw-56px))] -translate-y-1/2 rounded-r-xl border border-l-4 border-slate-200 border-l-gold bg-white p-3.5 text-slate-800 shadow-2xl motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-left-4 ${folding ? 'origin-left transition-all duration-700 motion-safe:scale-x-[0.04] motion-safe:scale-y-[0.2] opacity-0' : ''}`}
        >
          <button type="button" onClick={() => fold()} aria-label="Close" className="absolute right-2 top-2 text-slate-400 hover:text-slate-700">✕</button>
          {warn && !done && <p className="mb-2 rounded-md bg-gold px-2.5 py-1.5 text-xs font-extrabold text-ink motion-safe:animate-pulse">{t('warning')}</p>}
          {done ? (
            <p className="pr-5 text-sm font-semibold">{t('done')}</p>
          ) : (
            <>
              <p className="pr-5 text-[15px] font-extrabold">{t('title')}</p>
              <p className="mb-2.5 mt-0.5 text-xs text-slate-600">{t('text')}</p>
              <div className="flex overflow-hidden rounded-lg border-[1.5px] border-slate-200 bg-slate-50 focus-within:border-gold-dark">
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  maxLength={30} // the server takes 30 characters: a shorter box cut long numbers and saved a wrong one
                  placeholder="Your phone number"
                  aria-label="Phone number"
                  className="min-w-0 flex-1 bg-transparent px-2.5 py-2 text-sm font-semibold outline-none"
                />
                <button disabled={sending} className="btn-gold rounded-none px-3 text-[13px]">Get offer</button>
              </div>
              {error && <p className="mt-1.5 text-xs font-bold text-red-700">{error}</p>}
              {extra ? (
                <div className="mt-2 grid gap-1.5">
                  <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="Name" aria-label="Name" className="input !py-1.5" />
                  <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="Note, e.g. 3-in-1 sticks, 50k/month" aria-label="Note" className="input !py-1.5" />
                </div>
              ) : (
                <button type="button" onClick={() => setExtra(true)} className="mt-2 text-xs font-bold text-slate-500 hover:text-slate-800">+ Add name or a note (optional)</button>
              )}
              <p className="mt-2 text-[11px] text-slate-500">
                By clicking Get offer you agree to our{' '}
                <button type="button" onClick={() => setTerms((v) => !v)} aria-expanded={terms} className="font-bold text-gold-dark underline">quick T&amp;C</button>.
              </p>
              {terms && (
                <div className="mt-2 rounded-lg bg-ink p-2.5 text-xs leading-relaxed text-white">
                  {t('terms')}
                  <button type="button" onClick={() => setTerms(false)} className="mt-1.5 block rounded bg-gold px-2 py-0.5 text-[11px] font-extrabold text-ink">Got it</button>
                </div>
              )}
              {/* Hidden from people; robots fill it in and are quietly ignored by the server */}
              <input ref={honeypot} name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" className="absolute -left-[9999px] h-px w-px" />
            </>
          )}
        </form>
      )}
    </div>
  );
}
