'use client';
// The account corner of the staff portal (UI updates part 2, step 1): a round avatar with initials, a small
// menu under it (who you are, My profile, Log out), and the "are you sure?" popup before logging out.
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import type { Me } from '@/lib/api';
import Spinner from '@/components/ui/Spinner';

/** "Nishita Shirvi" -> "NS", "Vineet" -> "V". */
function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const two = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : (parts[0] ?? '?')[0];
  return two.toUpperCase();
}

/** Round badge with the person's initials. The gold ring marks the account (it matches the brand). */
export function Avatar({ name, className = 'h-9 w-9 text-sm' }: { name: string; className?: string }) {
  return (
    <span aria-hidden className={`inline-flex shrink-0 items-center justify-center rounded-full bg-ink font-bold text-gold-light ring-2 ring-gold ring-offset-2 ring-offset-white ${className}`}>
      {initials(name)}
    </span>
  );
}

/** `dark`: on the charcoal sidebar or menu header (lighter colours, so it stays readable). */
export function RoleBadge({ role, dark = false }: { role: Me['role']; dark?: boolean }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${role === 'admin' ? (dark ? 'bg-gold/20 text-gold-light' : 'bg-gold/20 text-gold-dark') : dark ? 'bg-emerald-400/20 text-emerald-200' : 'bg-emerald-100 text-emerald-800'}`}>
      {role === 'admin' ? 'Admin' : 'Staff'}
    </span>
  );
}

/** The "door with an arrow" log out icon (plain SVG, takes the text colour). */
export function LogoutIcon({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={className}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </svg>
  );
}

/** Top-right avatar button and its menu. `onLogout` opens the confirm popup (it lives in PortalShell). */
export default function AccountMenu({ me, onLogout }: { me: Me; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  // Closes on a click outside, or on Escape (focus goes back to the avatar). preventDefault on Escape so
  // the sidebar's own Escape handler knows this one was meant for the menu.
  useEffect(() => {
    if (!open) return;
    const click = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener('mousedown', click);
    window.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('mousedown', click);
      window.removeEventListener('keydown', key);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      <button
        ref={button}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="account-menu"
        aria-label={`Account: ${me.name}`}
        className="flex items-center gap-2 rounded-full p-1 pr-1 hover:bg-stone-100 md:pr-3"
      >
        <Avatar name={me.name} className="h-8 w-8 text-xs" />
        <span className="hidden text-sm font-semibold md:inline">{me.name.split(' ')[0]}</span>
        <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden className={`hidden h-4 w-4 text-slate-400 transition-transform md:block ${open ? 'rotate-180' : ''}`}>
          <path fillRule="evenodd" d="M5.2 7.2a.75.75 0 0 1 1.06 0L10 10.94l3.74-3.74a.75.75 0 1 1 1.06 1.06l-4.27 4.27a.75.75 0 0 1-1.06 0L5.2 8.26a.75.75 0 0 1 0-1.06z" />
        </svg>
      </button>
      {open && (
        <div
          id="account-menu"
          className="absolute right-0 z-50 mt-2 w-72 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border bg-white shadow-xl animate-in fade-in zoom-in-95 duration-150 motion-reduce:animate-none"
        >
          <div className="flex items-center gap-3 bg-gradient-to-br from-ink to-ink-soft p-4 text-white">
            <Avatar name={me.name} className="h-11 w-11 text-base ring-offset-ink" />
            <div className="min-w-0">
              <p className="truncate font-semibold">{me.name}</p>
              <p className="truncate text-xs text-stone-300">{me.email}</p>
              <div className="mt-1"><RoleBadge role={me.role} dark /></div>
            </div>
          </div>
          <div className="p-2">
            <Link href="/employee/me" onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-slate-100">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden className="h-4 w-4 text-slate-500">
                <circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" />
              </svg>
              My profile
            </Link>
            <button
              onClick={() => {
                setOpen(false);
                button.current?.focus(); // the popup gives focus back here when it closes
                onLogout();
              }}
              className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
            >
              <LogoutIcon />
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * "See you soon" popup before logging out. A native <dialog> opened with showModal(): the browser keeps the
 * focus inside it, closes it on Escape and gives the focus back to the button that opened it.
 * While logging out it can't be closed (Escape is ignored, Stay is disabled), so nobody clicks twice.
 */
export function LogoutDialog({ open, name, busy, onConfirm, onClose }: {
  open: boolean; name: string; busy: boolean; onConfirm: () => void; onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby="logout-title"
      onCancel={(e) => {
        e.preventDefault(); // Escape: we decide (stay open while busy)
        if (!busy) onClose();
      }}
      // The browser can still close it by force (Chrome: Escape pressed twice quickly can't be stopped).
      // Then the screen must know, or `open` stays true and the next "Log out" click does nothing
      // (PR #17 review). While logging out it is reopened: the log out carries on and shows its progress.
      onClose={() => {
        if (busy) ref.current?.showModal();
        else onClose();
      }}
      // A click on the dark area around the card (that is the <dialog> itself) means "Stay"
      onClick={(e) => e.target === ref.current && !busy && onClose()}
      className="w-[calc(100vw-2rem)] max-w-sm rounded-2xl p-0 shadow-2xl backdrop:bg-black/40 open:animate-in open:fade-in open:zoom-in-95 motion-reduce:open:animate-none"
    >
      <div className="p-6 text-center">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-gold/15 text-gold-dark">
          <LogoutIcon className="h-7 w-7" />
        </span>
        <h2 id="logout-title" className="mt-4 text-lg font-bold">See you soon, {name.split(' ')[0]}!</h2>
        <p className="mt-1 text-sm text-slate-500">You will need to log in again to use the portal.</p>
        <div className="mt-6 grid grid-cols-2 gap-2">
          <button onClick={onClose} disabled={busy} className="btn-ghost">Stay</button>
          <button onClick={onConfirm} disabled={busy} aria-busy={busy} className="btn bg-red-600 text-white hover:bg-red-700">
            {busy && <Spinner />}
            {busy ? 'Logging out…' : 'Log out'}
          </button>
        </div>
      </div>
    </dialog>
  );
}
