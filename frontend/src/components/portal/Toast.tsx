'use client';
// Toasts: small messages that pop up in the corner after an action ("Approved ✓") and go away by
// themselves (UI updates part 2, step 4). For results, not for errors in a form: those stay next to
// the form (Msg), so they don't vanish before someone has read them.
import { createContext, useCallback, useContext, useRef, useState } from 'react';

type Kind = 'ok' | 'error';
type Item = { id: number; text: string; kind: Kind };
type ToastFn = (text: string, kind?: Kind) => void;

const ToastContext = createContext<ToastFn>(() => undefined);

/** `const toast = useToast(); toast('Saved')` or `toast('Could not save', 'error')`. */
export const useToast = () => useContext(ToastContext);

const SHOW_MS = 3500;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const next = useRef(0);

  const close = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), []);
  const toast = useCallback<ToastFn>((text, kind = 'ok') => {
    const id = ++next.current;
    setItems((all) => [...all.slice(-2), { id, text, kind }]); // at most 3 on screen
    window.setTimeout(() => close(id), kind === 'error' ? SHOW_MS * 2 : SHOW_MS); // errors stay longer
  }, [close]);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {/* Always on the page, so screen readers announce each new message */}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-4 bottom-4 z-[60] flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:items-end">
        {items.map((t) => (
          <div
            key={t.id}
            role={t.kind === 'error' ? 'alert' : 'status'}
            className="pointer-events-auto flex w-full max-w-sm items-center gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm shadow-lg animate-in fade-in slide-in-from-bottom-4 duration-200 motion-reduce:animate-none"
          >
            <span aria-hidden className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${t.kind === 'ok' ? 'bg-emerald-600' : 'bg-red-600'}`}>
              {t.kind === 'ok' ? '✓' : '!'}
            </span>
            <span className="flex-1 font-medium text-stone-800">{t.text}</span>
            <button onClick={() => close(t.id)} aria-label="Close message" className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700">
              <span aria-hidden>✕</span>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
