'use client';
// Fades and slides a block in when it comes into view.
// Content is visible in the server HTML (Google and no-JS visitors see everything); only blocks that
// start below the screen are hidden after loading, then revealed. Off for "reduce motion" users, and
// everything is always visible when printing (print:… classes).
//
// Two modes, one animation (an entrance from above or from below, tailwindcss-animate):
// - once (default): page sections. Revealed the first time they come into view, then left alone.
//   All share ONE IntersectionObserver (shows blocks that come into view for any reason: scroll, a tab
//   switch that moves them up, a resize) and ONE scroll listener (shows blocks a fast scroll or a jump
//   such as "Explore the range" skipped over: those are above the screen and never "intersect").
// - repeat: cards in a grid (products, category tiles). Pop in EVERY time they come into view,
//   scrolling down or up. A card that is fully off screen is simply hidden; when it comes back into
//   view, the direction is chosen THEN: from the last real scroll movement (scrolling up: from above;
//   down: from below), or, with no recent scroll (e.g. a tab switch), from the edge it is at.
//
// stagger: cards in the same row appear one after another. The column is measured at the moment the
// card appears (so it is right after a tab switch, a reorder or a resize, and on 2 or 4 columns).
import { useEffect, useRef, useState } from 'react';

type Props = {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  stagger?: boolean;
  as?: 'div' | 'section' | 'li';
  repeat?: boolean;
};
// static: as the server rendered it (on screen at load, or motion off). hidden ⇄ fromAbove / fromBelow.
type State = 'static' | 'hidden' | 'fromAbove' | 'fromBelow';
const STAGGER_MS = 90;
const RECENT_SCROLL_MS = 300;

/** Column of a card in its grid row (0 = first), from where it really is on screen. */
function columnOf(el: Element): number {
  const parent = el.parentElement;
  const width = (el as HTMLElement).offsetWidth;
  if (!parent || !width) return 0;
  return Math.max(0, Math.round((el.getBoundingClientRect().left - parent.getBoundingClientRect().left) / width));
}

// ---------- scroll direction: the last real movement (no layout reads, just two numbers) ----------
let lastY = 0;
let scrolledUp: boolean | null = null;
let scrolledAt = 0;
let watchers = 0;
function onScrollDirection() {
  const y = window.scrollY;
  if (y !== lastY) {
    scrolledUp = y < lastY;
    scrolledAt = performance.now();
    lastY = y;
  }
}
function trackDirection(on: boolean) {
  if (on && watchers++ === 0) {
    lastY = window.scrollY;
    window.addEventListener('scroll', onScrollDirection, { passive: true });
  } else if (!on && --watchers === 0) {
    window.removeEventListener('scroll', onScrollDirection);
  }
}
/** Whether a block appearing now comes from above: the recent scroll direction, else where it is. */
function comesFromAbove(rect: DOMRectReadOnly): boolean {
  const recent = scrolledUp !== null && performance.now() - scrolledAt < RECENT_SCROLL_MS;
  return recent ? scrolledUp! : rect.top < 0;
}

// ---------- once ----------
const waiting = new Map<Element, () => void>();
let onceObserver: IntersectionObserver | null = null;

function show(el: Element) {
  const reveal = waiting.get(el);
  if (!reveal) return;
  waiting.delete(el);
  onceObserver?.unobserve(el);
  reveal();
  if (!waiting.size) window.removeEventListener('scroll', onScrollOnce);
}

function onScrollOnce() {
  for (const el of waiting.keys()) if (el.getBoundingClientRect().top < window.innerHeight) show(el);
}

function watchOnce(el: Element, reveal: () => void) {
  onceObserver ??= new IntersectionObserver((entries) => entries.forEach((e) => e.isIntersecting && show(e.target)), {
    rootMargin: '0px 0px -10% 0px',
  });
  if (!waiting.size) window.addEventListener('scroll', onScrollOnce, { passive: true });
  waiting.set(el, reveal);
  onceObserver.observe(el);
}

function unwatchOnce(el: Element) {
  if (waiting.delete(el)) onceObserver?.unobserve(el);
  if (!waiting.size) window.removeEventListener('scroll', onScrollOnce);
}

// ---------- repeat ----------
type Entry = { set: (s: State, column: number) => void; state: State; stagger: boolean };
const repeating = new Map<Element, Entry>();
let repeatObserver: IntersectionObserver | null = null;

function setRepeat(el: Element, state: State) {
  const entry = repeating.get(el);
  if (!entry || entry.state === state) return;
  entry.state = state;
  // The column is measured now, as the card appears: always the right ripple order
  entry.set(state, state !== 'hidden' && entry.stagger ? columnOf(el) : 0);
}

function watchRepeat(el: Element, entry: Entry) {
  // 0% visible (fully off screen): hidden. 15% visible: if it was hidden, it comes in. Cards already
  // on screen when the page loads stay as they are (no animation on load).
  repeatObserver ??= new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => {
        if (!e.isIntersecting) setRepeat(e.target, 'hidden');
        else if (e.intersectionRatio >= 0.15 && repeating.get(e.target)?.state === 'hidden')
          setRepeat(e.target, comesFromAbove(e.boundingClientRect) ? 'fromAbove' : 'fromBelow');
      }),
    { threshold: [0, 0.15] },
  );
  repeating.set(el, entry);
  repeatObserver.observe(el);
}

function unwatchRepeat(el: Element) {
  repeating.delete(el);
  repeatObserver?.unobserve(el);
}

export default function Reveal({ children, className = '', delay = 0, stagger = false, as: Tag = 'div', repeat = false }: Props) {
  const ref = useRef<HTMLElement>(null);
  const [state, setState] = useState<State>('static');
  const [column, setColumn] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    trackDirection(true);
    if (repeat) {
      watchRepeat(el, { state: 'static', stagger, set: (s, c) => { setColumn(c); setState(s); } });
      return () => { unwatchRepeat(el); trackDirection(false); };
    }
    if (el.getBoundingClientRect().top < window.innerHeight) { // already on screen or scrolled past
      trackDirection(false);
      return;
    }
    setState('hidden');
    watchOnce(el, () => {
      if (stagger) setColumn(columnOf(el));
      setState(comesFromAbove(el.getBoundingClientRect()) ? 'fromAbove' : 'fromBelow');
    });
    return () => { unwatchOnce(el); trackDirection(false); };
  }, [repeat, stagger]);

  // fill-mode-backwards: the start state is kept during the stagger delay, but nothing after the end, so
  // no transform is left that would trap a "position: fixed" popup inside the block.
  // print:…: a printed page or a saved PDF shows every block, not only the ones on screen.
  const enter = 'animate-in fade-in duration-700 ease-out fill-mode-backwards motion-reduce:animate-none';
  const motion = {
    static: '',
    hidden: 'opacity-0 print:opacity-100',
    fromAbove: `${enter} slide-in-from-top-8`,
    fromBelow: `${enter} slide-in-from-bottom-8`,
  }[state];
  const wait = delay + column * STAGGER_MS;
  return (
    <Tag
      ref={ref as React.Ref<never>}
      className={`${motion} ${className}`}
      style={state !== 'static' && state !== 'hidden' && wait ? { animationDelay: `${wait}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}
