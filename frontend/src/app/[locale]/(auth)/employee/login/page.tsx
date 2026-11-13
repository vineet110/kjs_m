'use client';
// Screen 04: staff login + sign up. Sign-ups wait for admin approval (no self-service access).
import Image from 'next/image';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState, useTransition } from 'react';
import Spinner from '@/components/ui/Spinner';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure, type Me } from '@/lib/api';
import { forgetAccount } from '@/lib/portal-session';
import { safeNext } from '@/lib/safe-url';
import { asset } from '@/lib/assets';
import { backToLogin, firebaseAuth, firebaseMessage, isWrongPassword, leaveFirebase, OLD_ACCOUNT_HINT } from '@/lib/firebase';
import { FirebaseError } from 'firebase/app';
import { createUserWithEmailAndPassword, sendEmailVerification, signInWithEmailAndPassword } from 'firebase/auth';

// Time limits, so the form is never locked with no way out: for the server to answer a login, and for the
// next page to open after it. (Not for sign-up: a slow sign-up may still succeed, and "failed" would mislead;
// a login that succeeds late does no harm, logging in again just works.)
const LOGIN_TIMEOUT_MS = 20_000;
const PAGE_OPEN_LIMIT_MS = 15_000;

function LoginInner() {
  const [tab, setTab] = useState<'login' | 'signup'>('login');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  // After a successful login: true until the next page has opened (React tracks the page change), so the
  // spinner carries on with no flash back to "Log in". If the page takes longer than PAGE_OPEN_LIMIT_MS,
  // the form is given back with a link to the page (slowTo), so nobody has to reload.
  // pageOpening: a page change we still wait for. Once it is "slow", it never locks the form again, also if
  // another attempt fails while that old page change is still pending.
  const [navigating, startNavigation] = useTransition();
  const [pageOpening, setPageOpening] = useState(false);
  const [slowTo, setSlowTo] = useState<string | null>(null);
  const slowTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(slowTimer.current), []);
  // The page change ended but this page is still here (e.g. the server sent us back to log in): no "you are
  // logged in, slow to open" notice, now or later
  useEffect(() => {
    if (navigating) return;
    window.clearTimeout(slowTimer.current);
    setPageOpening(false);
    setSlowTo(null);
  }, [navigating]);
  const working = busy || (navigating && pageOpening);
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next');
  // Just logged out (the portal sends `?bye=1`): say so once, then drop it from the address, so a reload
  // or a bookmark doesn't show it again
  const [bye, setBye] = useState(false);
  // A new person may log in on this tab: the portal must not show the previous person, even for a moment
  useEffect(() => forgetAccount(), []);
  useEffect(() => {
    if (params.get('bye') !== '1') return;
    setBye(true);
    const url = new URL(window.location.href);
    url.searchParams.delete('bye');
    window.history.replaceState(window.history.state, '', url);
  }, [params]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setBye(false);
    setError('');
    setNotice('');
    setSlowTo(null);
    window.clearTimeout(slowTimer.current);
    const email = String(f.email || '').trim();
    const password = String(f.password || '');
    const auth = firebaseAuth();
    try {
      if (tab === 'login') {
        // 1. Firebase checks the password. 2. Only a verified email may log in (anyone can make a Firebase
        // account with someone else's email). 3. Our API turns Firebase's proof into the normal session.
        const { user } = await signInWithEmailAndPassword(auth, email, password);
        if (!user.emailVerified) {
          await sendEmailVerification(user, backToLogin()).catch(() => undefined); // a fresh link, also for admin-made accounts
          await leaveFirebase();
          setNotice(`Please verify your email first: we sent a link to ${email}. Open it, then log in again.`);
          return;
        }
        const idToken = await user.getIdToken();
        const me = await api<Me>('/auth/login', { method: 'POST', body: { id_token: idToken }, timeoutMs: LOGIN_TIMEOUT_MS, safeToRepeat: true })
          .finally(leaveFirebase); // from here on, our session cookie is the login
        forgetAccount(); // also if this tab opened the login page without leaving the portal first
        const to = safeNext(next) ?? (me.role === 'admin' ? '/admin/dashboard' : '/employee/dashboard');
        setPageOpening(true);
        startNavigation(() => router.replace(to));
        slowTimer.current = window.setTimeout(() => {
          setPageOpening(false);
          setSlowTo(to);
        }, PAGE_OPEN_LIMIT_MS);
      } else {
        // The Firebase account first (it keeps the password), then ours (waits for admin approval). If an
        // earlier try made the Firebase account but stopped before ours, signing in finishes it.
        let user;
        try {
          user = (await createUserWithEmailAndPassword(auth, email, password)).user;
        } catch (err) {
          if (!(err instanceof FirebaseError) || err.code !== 'auth/email-already-in-use') throw err;
          user = (await signInWithEmailAndPassword(auth, email, password).catch(() => { throw err; })).user;
        }
        if (!user.emailVerified) await sendEmailVerification(user, backToLogin()).catch(() => undefined);
        const idToken = await user.getIdToken();
        await api('/auth/signup', { method: 'POST', body: { id_token: idToken, name: f.name, phone: f.phone } })
          .finally(leaveFirebase);
        setNotice(`Account created. Open the link we emailed to ${email} to verify it. An admin will then approve your account.`);
        setTab('login');
      }
    } catch (err) {
      if (err instanceof ApiFailure) {
        const fields = Object.values(err.body.details || {}).join(' ');
        setError(fields ? `${err.message} ${fields}` : err.message);
      } else if (err instanceof FirebaseError) {
        setError(tab === 'login' && isWrongPassword(err) ? `${firebaseMessage(err)} ${OLD_ACCOUNT_HINT}` : firebaseMessage(err));
      }
      else setError('Could not reach the server.');
    } finally {
      setBusy(false);
    }
  }
  const label = tab === 'login' ? (working ? 'Logging in…' : 'Log in') : working ? 'Creating account…' : 'Create account';

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink p-4">
      <div className="w-full max-w-md space-y-6">
        <Link href="/" className="flex justify-center">
          <Image src={asset('/images/kjs/logo/Kjs.png')} alt="KJS India" width={160} height={36} className="h-9 w-auto" />
        </Link>
        <div className="card space-y-5 p-6">
          {bye && (
            <p role="status" className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-semibold text-emerald-800 animate-in fade-in slide-in-from-top-2 motion-reduce:animate-none">
              <span aria-hidden className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-600 text-xs text-white">✓</span>
              You&apos;ve logged out safely. See you soon!
            </p>
          )}
          <div>
            <h1 className="text-xl font-bold">Staff portal</h1>
            <p className="text-sm text-slate-500">Approved KJS staff only.</p>
          </div>
          <div className="grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-sm font-semibold">
            {(['login', 'signup'] as const).map((t) => (
              <button
                key={t}
                disabled={working}
                onClick={() => { setTab(t); setError(''); setSlowTo(null); }}
                className={`rounded-md py-1.5 disabled:cursor-not-allowed disabled:opacity-50 ${tab === t ? 'bg-white shadow-sm' : 'text-slate-500'}`}
              >
                {t === 'login' ? 'Log in' : 'Sign up'}
              </button>
            ))}
          </div>
          <form onSubmit={submit} className="space-y-3">
            {tab === 'signup' && (
              <>
                <div><label className="label" htmlFor="name">Full name</label><input id="name" name="name" required minLength={2} className="input" /></div>
                <div><label className="label" htmlFor="phone">Phone *</label><PhoneInput id="phone" maxLength={20} placeholder="Phone" /></div>
              </>
            )}
            <div><label className="label" htmlFor="email">Work email</label><input id="email" name="email" type="email" required className="input" autoComplete="username" /></div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" name="password" type="password" required minLength={tab === 'signup' ? 10 : 1} className="input" autoComplete={tab === 'login' ? 'current-password' : 'new-password'} />
              {tab === 'signup' && <p className="mt-1 text-xs text-slate-500">At least 10 characters.</p>}
              {tab === 'login' && (
                <Link href="/employee/forgot-password" className="mt-1 inline-block text-xs font-semibold text-sky-700 hover:underline">
                  Forgot password?
                </Link>
              )}
            </div>
            {notice && <p className="rounded bg-emerald-50 p-2 text-sm text-emerald-800">{notice}</p>}
            {slowTo && (
              <p role="status" className="rounded bg-amber-50 p-2 text-sm text-amber-900">
                You are logged in, but the page is slow to open. <a href={slowTo} className="font-semibold underline">Open it</a>
              </p>
            )}
            {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
            <button disabled={working} aria-busy={working} className="btn-dark w-full">
              {working && <Spinner />}
              {label}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
