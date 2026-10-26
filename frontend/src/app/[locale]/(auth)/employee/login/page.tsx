'use client';
// Screen 04: staff login + sign up. Sign-ups wait for admin approval (no self-service access).
import Image from 'next/image';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';
import { api, ApiFailure, type Me } from '@/lib/api';
import { safeNext } from '@/lib/safe-url';

function LoginInner() {
  const [tab, setTab] = useState<'login' | 'signup'>('login');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const router = useRouter();
  const next = useSearchParams().get('next');

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (tab === 'login') {
        const me = await api<Me>('/auth/login', { method: 'POST', body: { email: f.email, password: f.password } });
        const home = me.role === 'admin' ? '/admin/dashboard' : '/employee/dashboard';
        router.replace(safeNext(next) ?? home);
      } else {
        await api('/auth/signup', { method: 'POST', body: { name: f.name, email: f.email, phone: f.phone, password: f.password } });
        setNotice('Account created. An admin will approve it; then you can log in.');
        setTab('login');
      }
    } catch (err) {
      if (err instanceof ApiFailure) {
        const fields = Object.values(err.body.details || {}).join(' ');
        setError(fields ? `${err.message} ${fields}` : err.message);
      } else setError('Could not reach the server.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink p-4">
      <div className="w-full max-w-md space-y-6">
        <Link href="/" className="flex justify-center">
          <Image src="/images/kjs/logo/Kjs.png" alt="KJS India" width={160} height={36} className="h-9 w-auto" />
        </Link>
        <div className="card space-y-5 p-6">
          <div>
            <h1 className="text-xl font-bold">Staff portal</h1>
            <p className="text-sm text-slate-500">Approved KJS staff only.</p>
          </div>
          <div className="grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-sm font-semibold">
            {(['login', 'signup'] as const).map((t) => (
              <button key={t} onClick={() => { setTab(t); setError(''); }} className={`rounded-md py-1.5 ${tab === t ? 'bg-white shadow-sm' : 'text-slate-500'}`}>
                {t === 'login' ? 'Log in' : 'Sign up'}
              </button>
            ))}
          </div>
          <form onSubmit={submit} className="space-y-3">
            {tab === 'signup' && (
              <>
                <div><label className="label" htmlFor="name">Full name</label><input id="name" name="name" required minLength={2} className="input" /></div>
                <div><label className="label" htmlFor="phone">Phone</label><input id="phone" name="phone" className="input" /></div>
              </>
            )}
            <div><label className="label" htmlFor="email">Work email</label><input id="email" name="email" type="email" required className="input" autoComplete="username" /></div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" name="password" type="password" required minLength={tab === 'signup' ? 10 : 1} className="input" autoComplete={tab === 'login' ? 'current-password' : 'new-password'} />
              {tab === 'signup' && <p className="mt-1 text-xs text-slate-500">At least 10 characters.</p>}
            </div>
            {notice && <p className="rounded bg-emerald-50 p-2 text-sm text-emerald-800">{notice}</p>}
            {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
            <button disabled={busy} className="btn-dark w-full">{busy ? 'Please wait…' : tab === 'login' ? 'Log in' : 'Create account'}</button>
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
