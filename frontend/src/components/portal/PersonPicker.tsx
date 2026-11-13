'use client';
// Pick one colleague by typing part of their name or employee code (instead of scrolling a long list).
// Arrow keys move through the matches, Enter picks, Escape closes. Empty = nobody ("No one" in `emptyLabel`).
// A small combobox of our own (no extra package); the value is the person's id as a string, '' for nobody.
import { useId, useMemo, useState } from 'react';
import { matchPeople, type Person } from '@/lib/people';

export default function PersonPicker({ id, people, value, onChange, emptyLabel }: {
  id: string; people: Person[]; value: string; onChange: (id: string) => void; emptyLabel: string;
}) {
  const listId = useId();
  const picked = people.find((p) => String(p.id) === value) ?? null;
  const [text, setText] = useState<string | null>(null); // null = not typing: the input shows the picked person
  const [at, setAt] = useState(0);
  const open = text !== null;
  const matches = useMemo(() => (open ? matchPeople(people, text) : []), [open, people, text]);
  const label = (p: Person) => (p.employee_code ? `${p.name} (${p.employee_code})` : p.name);

  function choose(p: Person | null) {
    onChange(p ? String(p.id) : '');
    setText(null);
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) setText('');
      const n = matches.length;
      if (n) setAt((i) => (e.key === 'ArrowDown' ? (i + 1) % n : (i - 1 + n) % n));
    } else if (e.key === 'Enter' && open) {
      e.preventDefault(); // not the form's submit
      if (matches[at]) choose(matches[at]);
    } else if (e.key === 'Escape' && open) {
      e.preventDefault();
      setText(null);
    }
  }

  return (
    <div className="relative">
      <div className="flex gap-1">
        <input
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && matches[at] ? `${listId}-${matches[at].id}` : undefined}
          value={open ? text : picked ? label(picked) : ''}
          placeholder={picked ? undefined : `${emptyLabel} · type a name or code`}
          onFocus={() => { setText(''); setAt(0); }}
          onChange={(e) => { setText(e.target.value); setAt(0); }}
          onKeyDown={onKey}
          onBlur={() => setTimeout(() => setText(null), 150)} // after a click on a match
          className="input"
          autoComplete="off"
        />
        {picked && !open && (
          <button type="button" onClick={() => choose(null)} aria-label={`Clear: ${emptyLabel}`} className="btn-ghost px-2">✕</button>
        )}
      </div>
      {open && (
        <ul id={listId} role="listbox" className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border bg-white text-sm shadow-lg">
          <li role="option" aria-selected={false} onMouseDown={(e) => { e.preventDefault(); choose(null); }}
            className="cursor-pointer px-3 py-2 text-slate-500 hover:bg-slate-50">{emptyLabel}</li>
          {matches.length === 0 && <li className="px-3 py-2 text-slate-400">Nobody matches “{text}”.</li>}
          {matches.map((p, i) => (
            <li key={p.id} id={`${listId}-${p.id}`} role="option" aria-selected={i === at}
              onMouseDown={(e) => { e.preventDefault(); choose(p); }}
              className={`cursor-pointer px-3 py-2 ${i === at ? 'bg-slate-100' : 'hover:bg-slate-50'}`}>
              {p.name}{p.employee_code ? <span className="ml-1 text-xs text-slate-500">{p.employee_code}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
