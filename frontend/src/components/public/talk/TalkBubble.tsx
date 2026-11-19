'use client';
// The site talks (site_ui.ini talk): one small speech bubble, shared by every message, so only one shows
// at a time.
// - Mouse: hovering anything marked data-say="<key>" shows its message (texts talk.<key>, Admin > Text & SEO).
// - Keyboard: the same on focus.
// - Nudges, each once per visit: Koko after idle_seconds without a move; after the first product goes into the
//   enquiry list; phones (no hover): Koko, then WhatsApp, after phone_*_seconds.
// - Never over a popup window or the open Koko chat. "Reduce motion": the bubble still shows, without moving.
import { useCallback, useEffect, useRef, useState } from 'react';
import type { SiteUi } from '@/lib/api';
import { once, somethingOpen, useTalkPage } from './useTalkPage';

type Props = { texts: Record<string, string>; ui: SiteUi };
type Shown = { text: string; x: number; y: number; arrow: number; below: boolean };
const GAP = 12; // px between the bubble and what it points at
const WIDTH = 260;

/** The box to point at: a wrapper with display:contents has no box of its own, so its first child. */
function boxOf(el: Element): DOMRect {
  const r = el.getBoundingClientRect();
  return r.width || r.height || !el.firstElementChild ? r : el.firstElementChild.getBoundingClientRect();
}

export default function TalkBubble({ texts, ui }: Props) {
  const here = useTalkPage(!!ui.talk_all_pages);
  const on = ui.enabled && ui.talk === true && here; // an older API without the switch: silent
  const [shown, setShown] = useState<Shown | null>(null);
  const target = useRef<Element | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const shownText = useRef(''); // the text on show, for following the page as it scrolls
  shownText.current = shown?.text ?? '';
  const say = useCallback((key: string) => texts[`talk.${key}`] ?? '', [texts]);

  const place = useCallback((el: Element, text: string) => {
    const r = boxOf(el);
    const w = Math.min(WIDTH, window.innerWidth - 20);
    const x = Math.max(10, Math.min(window.innerWidth - w - 10, r.left + r.width / 2 - w / 2));
    const below = r.top < 90; // no room above (e.g. the header button): under it
    setShown({ text, x, y: below ? r.bottom + GAP : r.top - GAP, below, arrow: Math.max(14, Math.min(w - 14, r.left + r.width / 2 - x)) });
  }, []);
  const hide = useCallback(() => { clearTimeout(timer.current); target.current = null; setShown(null); }, []);
  const show = useCallback((el: Element, text: string, ms?: number) => {
    if (!text || somethingOpen()) return;
    clearTimeout(timer.current);
    target.current = el;
    place(el, text);
    if (ms) timer.current = setTimeout(hide, ms);
  }, [place, hide]);
  /** A nudge: once per visit, for bubble_seconds, at `selector` (or Koko when that is off screen). */
  const nudge = useCallback((el: Element | null, key: string, onceKey: string) => {
    if (once.done(onceKey)) return;
    const koko = document.querySelector('[data-say="koko"]');
    const r = el?.getBoundingClientRect();
    const visible = r && r.bottom > 0 && r.top < window.innerHeight && (r.width || r.height);
    const at = visible ? el : koko;
    if (!at || somethingOpen()) return;
    once.mark(onceKey);
    show(at, say(key), (ui.bubble_seconds ?? 5) * 1000);
  }, [say, show, ui.bubble_seconds]);

  // Hover and focus
  useEffect(() => {
    if (!on) return;
    const mouse = window.matchMedia('(hover: hover)').matches;
    const over = (e: Event) => {
      const el = (e.target as Element | null)?.closest?.('[data-say]');
      if (el && el !== target.current) show(el, say((el as HTMLElement).dataset.say!));
    };
    const out = (e: Event) => {
      const el = (e.target as Element | null)?.closest?.('[data-say]');
      const to = (e as PointerEvent | FocusEvent).relatedTarget as Node | null;
      if (el && el === target.current && !(to && el.contains(to))) hide();
    };
    if (mouse) {
      document.addEventListener('pointerover', over);
      document.addEventListener('pointerout', out);
    }
    document.addEventListener('focusin', over);
    document.addEventListener('focusout', out);
    // Follow what it points at while the page scrolls
    const follow = () => { if (target.current) place(target.current, shownText.current); };
    window.addEventListener('scroll', follow, { passive: true });
    window.addEventListener('resize', follow);
    return () => {
      document.removeEventListener('pointerover', over);
      document.removeEventListener('pointerout', out);
      document.removeEventListener('focusin', over);
      document.removeEventListener('focusout', out);
      window.removeEventListener('scroll', follow);
      window.removeEventListener('resize', follow);
    };
  }, [on, say, show, hide, place]);
  // Nudges: idle Koko, phones, first enquiry-list product
  useEffect(() => {
    if (!on) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let idle: ReturnType<typeof setTimeout>;
    const resetIdle = () => {
      clearTimeout(idle);
      idle = setTimeout(() => { if (!target.current) nudge(null, 'idle', 'idle'); }, (ui.idle_seconds ?? 20) * 1000);
    };
    const moves = ['pointermove', 'scroll', 'keydown', 'touchstart'] as const;
    moves.forEach((m) => window.addEventListener(m, resetIdle, { passive: true }));
    resetIdle();
    if (!window.matchMedia('(hover: hover)').matches) {
      timers.push(setTimeout(() => nudge(document.querySelector('[data-say="koko"]'), 'koko', 'phone-koko'), (ui.phone_koko_seconds ?? 6) * 1000));
      timers.push(setTimeout(() => nudge(document.querySelector('[data-say="whatsapp"]'), 'whatsapp', 'phone-whatsapp'), (ui.phone_whatsapp_seconds ?? 16) * 1000));
    }
    // The enquiry list (lib/history.ts) says when it changes: the first product added gets a cheer
    let count: number | null = null;
    const listChanged = (e: Event) => {
      const n = (e as CustomEvent<number>).detail;
      // At the button just clicked; Safari doesn't focus buttons, so <body> means: point at Koko instead
      const clicked = document.activeElement;
      const at = clicked && clicked !== document.body && clicked !== document.documentElement ? clicked : null;
      if (count === 0 && n === 1) nudge(at, 'enquiry_added', 'enquiry');
      count = n;
    };
    window.addEventListener('kjs:enquiry-list', listChanged);
    try { count = (JSON.parse(localStorage.getItem('kjs_enquiry_list') ?? '[]') as unknown[]).length; } catch { count = 0; }
    return () => {
      clearTimeout(idle);
      timers.forEach(clearTimeout);
      moves.forEach((m) => window.removeEventListener(m, resetIdle));
      window.removeEventListener('kjs:enquiry-list', listChanged);
    };
  }, [on, nudge, ui.idle_seconds, ui.phone_koko_seconds, ui.phone_whatsapp_seconds]);

  if (!on || !shown) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className={`pointer-events-none fixed z-[70] max-w-[260px] rounded-xl bg-ink px-3.5 py-2 text-[13px] font-semibold leading-snug text-white shadow-xl ring-1 ring-gold/40 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-200 ${shown.below ? '' : '-translate-y-full'}`}
      style={{ left: shown.x, top: shown.y, width: 'max-content' }}
    >
      {shown.text}
      <span
        aria-hidden="true"
        className={`absolute h-3 w-3 rotate-45 bg-ink ${shown.below ? '-top-1.5' : '-bottom-1.5'}`}
        style={{ left: shown.arrow - 6 }}
      />
    </div>
  );
}
