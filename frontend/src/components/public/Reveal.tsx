'use client';
// Fades and slides a block in when it comes into view.
// Content is visible in the server HTML (Google and no-JS visitors see everything); only blocks that
// start below the screen are hidden after loading, then revealed. Off for "reduce motion" users, and
// everything is always visible when printing (print:… classes).
//
// Two modes:
// - once (default): page sections. Revealed the first time they come into view, then left alone.
//   All share ONE IntersectionObserver (shows blocks that come into view for any reason: scroll, a tab
//   switch that moves them up, a resize) and ONE scroll listener (shows blocks a fast scroll or a jump
//   such as "Explore the range" skipped over: those are above the screen and never "intersect").
// - repeat: cards in a grid (products, category tiles). Pop in EVERY time they come into view,
//   scrolling down or up: a card that is fully off screen is hidden on the side it is on, so it slides
//   in from below when scrolling down and from above when scrolling up. One shared check (at most once
//   per frame, on scroll and when the page height changes) keeps that side right for cards a jump or a
//   tab switch carried past without them ever "intersecting".
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
type State = 'static' | 'below' | 'above' | 'shown';
const STAGGER_MS = 90;

/** Column of a card in its grid row (0 = first), from where it really is on screen. */
function columnOf(el: Element): number {
  const parent = el.parentElement;
  const width = (el as HTMLElement).offsetWidth;
  if (!parent || !width) return 0;
  return Math.max(0, Math.round((el.getBoundingClientRect().left - parent.getBoundingClientRect().left) / width));
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
let pageObserver: ResizeObserver | null = null;
let frame = 0;

function setRepeat(el: Element, state: State) {
  const entry = repeating.get(el);
  if (!entry || entry.state === state) return;
  entry.state = state;
  // The column is measured now, as the card appears: always the right ripple order
  entry.set(state, state === 'shown' && entry.stagger ? columnOf(el) : 0);
}

// Hidden cards keep the side they are on up to date (a jump or a tab switch can carry them past
// the screen without them ever "intersecting"). Runs at most once per frame.
function checkSides() {
  frame = 0;
  for (const [el, entry] of repeating) {
    if (entry.state !== 'below' && entry.state !== 'above') continue;
    const r = el.getBoundingClientRect();
    if (r.bottom < 0) setRepeat(el, 'above');
    else if (r.top > window.innerHeight) setRepeat(el, 'below');
  }
}
function scheduleSides() {
  if (!frame) frame = requestAnimationFrame(checkSides);
}

function watchRepeat(el: Element, entry: Entry) {
  // 15% visible: pop in. 0% visible (fully off screen): hidden, on the side it is on.
  repeatObserver ??= new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => {
        if (e.intersectionRatio >= 0.15) setRepeat(e.target, 'shown');
        else if (!e.isIntersecting) setRepeat(e.target, e.boundingClientRect.top < 0 ? 'above' : 'below');
      }),
    { threshold: [0, 0.15] },
  );
  if (!repeating.size) {
    window.addEventListener('scroll', scheduleSides, { passive: true });
    pageObserver ??= new ResizeObserver(scheduleSides); // page height changed (e.g. a tab switch)
    pageObserver.observe(document.body);
  }
  repeating.set(el, entry);
  repeatObserver.observe(el);
}

function unwatchRepeat(el: Element) {
  repeating.delete(el);
  repeatObserver?.unobserve(el);
  if (!repeating.size) {
    window.removeEventListener('scroll', scheduleSides);
    pageObserver?.disconnect();
  }
}

export default function Reveal({ children, className = '', delay = 0, stagger = false, as: Tag = 'div', repeat = false }: Props) {
  const ref = useRef<HTMLElement>(null);
  const [state, setState] = useState<State>('static');
  const [column, setColumn] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (repeat) {
      watchRepeat(el, { state: 'static', stagger, set: (s, c) => { setColumn(c); setState(s); } });
      return () => unwatchRepeat(el);
    }
    if (el.getBoundingClientRect().top < window.innerHeight) return; // already on screen or scrolled past
    setState('below');
    watchOnce(el, () => {
      if (stagger) setColumn(columnOf(el));
      setState('shown');
    });
    return () => unwatchOnce(el);
  }, [repeat, stagger]);

  // Hidden states have no transition (the block is off screen, so the jump can't be seen). "shown" ends
  // at transform: none, so a block never keeps a transform that would trap a fixed popup inside it.
  // print:…: a printed page or a saved PDF shows every card, not only the ones on screen.
  const motion = {
    static: '',
    below: 'translate-y-8 opacity-0 transition-none print:transform-none print:opacity-100',
    above: '-translate-y-8 opacity-0 transition-none print:transform-none print:opacity-100',
    shown: 'transform-none opacity-100 transition-[opacity,transform] duration-700 ease-out',
  }[state];
  const wait = delay + column * STAGGER_MS;
  return (
    <Tag
      ref={ref as React.Ref<never>}
      className={`${motion} ${className}`}
      style={state === 'shown' && wait ? { transitionDelay: `${wait}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}
