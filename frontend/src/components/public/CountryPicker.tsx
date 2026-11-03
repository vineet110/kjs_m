'use client';
// Phone code picker and country picker (UI step 7), one search list for both:
// - a button shows the flag (+ code or name); it opens a list with a search box. Typing letters shows the
//   countries starting with them, typing digits (or +9…) the phone codes starting with them.
// - keyboard: ↑ ↓ move, Enter picks, Escape closes (focus back on the button); a click outside closes.
// - flags are SVG files in public/flags (no package); two regions without one show their letter code.
// What the forms send is unchanged: a hidden input with the phone ("+91 98765 43210") or the country name.
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import {
  composePhone, countryByCode, countryByName, DEFAULT_COUNTRY, filterCountries, NO_FLAG, phoneLooksValid, splitPhone,
  type Country,
} from '@/lib/countries';

const LAST_KEY = 'kjs_phone_country'; // the last phone code picked on this device (decision 2a)

function Flag({ code }: { code: string }) {
  if (NO_FLAG.has(code)) {
    return <span className="inline-flex h-[15px] w-5 shrink-0 items-center justify-center rounded-sm bg-slate-200 text-[8px] font-bold">{code}</span>;
  }
  // eslint-disable-next-line @next/next/no-img-element -- a tiny local SVG; next/image would need SVGs turned on
  return <img src={`/flags/${code.toLowerCase()}.svg`} alt="" width={20} height={15} loading="lazy" className="h-[15px] w-5 shrink-0 rounded-sm object-cover shadow-sm" />;
}

/** The open list: a search box and the matching countries. */
function CountryList({ selected, showDial, up, onPick, onClose }: {
  selected: string | null; showDial: boolean; up: boolean; onPick: (c: Country) => void; onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const matches = useMemo(() => filterCountries(query), [query]);
  const [active, setActive] = useState(0);
  const listId = useId();
  const list = useRef<HTMLUListElement>(null);

  // Start on the selected country; a new search starts at the top
  useEffect(() => {
    const i = query ? 0 : Math.max(0, matches.findIndex((c) => c.code === selected));
    setActive(i);
  }, [query, matches, selected]);
  useEffect(() => {
    list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => Math.min(Math.max(i + (e.key === 'ArrowDown' ? 1 : -1), 0), matches.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault(); // never submits the form
      if (matches[active]) onPick(matches[active]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation(); // closes only the list, not a window around it (Koko, the enquiry form)
      onClose();
    } else if (e.key === 'Tab') {
      onClose();
    }
  }

  return (
    <div className={`absolute left-0 z-50 ${up ? 'bottom-full mb-1' : 'top-full mt-1'} w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-slate-200 bg-white p-2 shadow-xl`}>
      <input
        autoFocus
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKey}
        placeholder={showDial ? 'Search country or code' : 'Search country'}
        className="input !py-1.5 text-sm"
        role="combobox"
        aria-expanded="true"
        aria-controls={listId}
        aria-activedescendant={matches[active] ? `${listId}-${matches[active].code}` : undefined}
        aria-label={showDial ? 'Search country or phone code' : 'Search country'}
      />
      <ul ref={list} id={listId} role="listbox" className="mt-1 max-h-60 overflow-y-auto text-sm">
        {matches.length === 0 && <li className="px-2 py-2 text-slate-500">No match</li>}
        {matches.map((c, i) => (
          <li
            key={c.code}
            id={`${listId}-${c.code}`}
            data-index={i}
            role="option"
            aria-selected={c.code === selected}
            onMouseDown={(e) => e.preventDefault()} // keep focus in the search box
            onClick={() => onPick(c)}
            onMouseMove={() => setActive(i)}
            className={`flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 ${i === active ? 'bg-gold-light/50' : ''} ${c.code === selected ? 'font-semibold' : ''}`}
          >
            <Flag code={c.code} />
            <span className="flex-1 truncate">{c.name}</span>
            {showDial && <span className="text-slate-500">+{c.dial}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Whether the list should open upward: not enough room below the button, and more room above. Room is
 * measured inside the nearest box that scrolls or cuts off its content (Koko's chat area, the enquiry
 * pop-up), not just the window, so the list never opens past that box's edge.
 */
function opensUp(button: HTMLElement): boolean {
  let top = 0;
  let bottom = window.innerHeight;
  for (let el = button.parentElement; el; el = el.parentElement) {
    if (/auto|scroll|hidden/.test(getComputedStyle(el).overflowY)) {
      const box = el.getBoundingClientRect();
      top = Math.max(top, box.top);
      bottom = Math.min(bottom, box.bottom);
      break;
    }
  }
  const r = button.getBoundingClientRect();
  return bottom - r.bottom < 330 && r.top - top > bottom - r.bottom;
}

/** A button that opens the list; closes on a click outside. */
function Picker({ id, label, selected, showDial, buttonClass, children, onPick, buttonRef }: {
  id?: string; label: string; selected: string | null; showDial: boolean; buttonClass: string; children: React.ReactNode;
  onPick: (c: Country) => void; buttonRef?: React.RefObject<HTMLButtonElement | null>;
}) {
  const [open, setOpen] = useState(false);
  const [up, setUp] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const ownButton = useRef<HTMLButtonElement>(null);
  const button = buttonRef ?? ownButton;

  useEffect(() => {
    if (!open) return;
    const outside = (e: PointerEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);

  const close = () => {
    setOpen(false);
    button.current?.focus();
  };
  return (
    <div ref={box} className="relative">
      <button type="button" id={id} ref={button} onClick={() => {
          if (button.current) setUp(opensUp(button.current));
          setOpen(!open);
        }} aria-haspopup="listbox" aria-expanded={open} aria-label={label} className={buttonClass}>
        {children}
        <span aria-hidden className="text-[10px] text-slate-400">▼</span>
      </button>
      {open && <CountryList selected={selected} showDial={showDial} up={up} onPick={(c) => { onPick(c); close(); }} onClose={close} />}
    </div>
  );
}

type PhoneProps = {
  id: string;
  name?: string;
  defaultValue?: string | null;
  maxLength?: number; // of the whole saved phone ("+91 …"), the database column size
  placeholder?: string;
  /** The country picked in a country field next to it: the code follows it until the visitor picks one (4a). */
  linkedCountry?: string | null;
};

/**
 * Phone field with a country code picker. Sends "+code number" in a hidden input called `name`.
 * A saved phone is sent back exactly as it was until the person changes the code or the number, so saving
 * something else (a profile's notification settings) never rewrites or blocks an older number.
 */
export function PhoneInput({ id, name = 'phone', defaultValue, maxLength = 30, placeholder = 'Phone / WhatsApp', linkedCountry }: PhoneProps) {
  const saved = (defaultValue ?? '').trim();
  const [code, setCode] = useState(() => splitPhone(saved).code);
  const [number, setNumber] = useState(() => splitPhone(saved).number);
  const [edited, setEdited] = useState(!saved);
  const userPicked = useRef(!!saved); // a saved phone keeps its code; nothing else replaces it
  const input = useRef<HTMLInputElement>(null);
  const country = countryByCode(code) ?? countryByCode(DEFAULT_COUNTRY)!;
  const composed = composePhone(country.dial, number);

  useEffect(() => {
    try {
      const last = localStorage.getItem(LAST_KEY);
      if (!countryByCode(last)) return;
      // A saved "+1 …" reads back as the code picked last on this device if it shares the code (Canada)
      if (saved) setCode(splitPhone(saved, last!).code);
      else setCode(last!); // nothing saved: start on the code picked last on this device (2a)
    } catch { /* storage blocked: keep the default */ }
  }, [saved]);
  // Follow the country field until the person picks a code themselves (4a)
  useEffect(() => {
    if (linkedCountry && !userPicked.current && countryByCode(linkedCountry)) setCode(linkedCountry);
  }, [linkedCountry]);
  // The browser refuses to send the form while an edited number doesn't look right (5a), or no longer fits
  // after a longer code was picked
  useEffect(() => {
    const problem = !edited ? ''
      : !phoneLooksValid(number, country.dial) ? 'Please enter digits only (6 to 15 with the country code).'
      : composed.length > maxLength ? `Too long: at most ${maxLength} characters with the country code.`
      : '';
    input.current?.setCustomValidity(problem);
  }, [edited, number, country.dial, composed, maxLength]);

  function pick(c: Country) {
    userPicked.current = true;
    setEdited(true);
    setCode(c.code);
    try { localStorage.setItem(LAST_KEY, c.code); } catch { /* storage blocked */ }
  }

  return (
    <div className="flex gap-2">
      <Picker
        label={`Country code: ${country.name} +${country.dial}`}
        selected={code}
        showDial
        onPick={pick}
        buttonClass="input flex !w-auto shrink-0 items-center gap-1.5 whitespace-nowrap"
      >
        <Flag code={country.code} />
        <span className="text-sm">+{country.dial}</span>
      </Picker>
      <input
        ref={input}
        id={id}
        type="tel"
        inputMode="tel"
        autoComplete="tel-national"
        value={number}
        onChange={(e) => { setNumber(e.target.value); setEdited(true); }}
        maxLength={Math.max(6, maxLength - country.dial.length - 2)}
        placeholder={placeholder}
        className="input min-w-0 flex-1"
      />
      <input type="hidden" name={name} value={edited ? composed : saved} />
    </div>
  );
}

type CountryProps = {
  id: string;
  name?: string;
  defaultValue?: string | null; // the saved country name
  required?: boolean;
  onChange?: (code: string) => void;
};

/**
 * Country field from the list only (decision 3a). Sends the English country name in a hidden input.
 * An older saved country that isn't a list name ("UAE") is shown and sent as it was until one is picked.
 */
export function CountrySelect({ id, name = 'country', defaultValue, required, onChange }: CountryProps) {
  const saved = (defaultValue ?? '').trim();
  const [code, setCode] = useState<string | null>(() => (saved ? countryByName(saved)?.code ?? null : null));
  const [missing, setMissing] = useState(false);
  const country = countryByCode(code);
  const shown = country?.name ?? saved; // the old text until a country is picked
  return (
    <div className="relative">
      <Picker
        id={id}
        label={shown ? `Country: ${shown}` : 'Choose a country'}
        selected={code}
        showDial={false}
        onPick={(c) => { setCode(c.code); setMissing(false); onChange?.(c.code); }}
        buttonClass={`input flex items-center gap-2 text-left ${missing ? '!border-red-500' : ''}`}
      >
        {country ? <Flag code={country.code} /> : null}
        <span className={`flex-1 truncate ${shown ? '' : 'text-slate-400'}`}>{shown || 'Choose a country'}</span>
      </Picker>
      {/* Lets the browser's "required" check cover the picker; our own message replaces its bubble */}
      <input
        tabIndex={-1}
        aria-hidden
        name={name}
        value={shown}
        onChange={() => {}}
        onInvalid={(e) => {
          e.preventDefault();
          setMissing(true);
          document.getElementById(id)?.focus();
        }}
        required={required}
        className="pointer-events-none absolute bottom-0 left-0 h-0 w-0 opacity-0"
      />
      {missing && <p role="alert" className="mt-1 text-xs text-red-600">Please choose a country.</p>}
    </div>
  );
}
