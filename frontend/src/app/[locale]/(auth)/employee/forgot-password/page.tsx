'use client';
// Forgot password: Firebase emails a reset link and shows its own "new password" page; afterwards it sends
// the person back to our login page. Opens without a login (proxy.ts NO_LOGIN_PAGES).
// The answer is the same for every email (it never says whether an account exists).
import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import { FirebaseError } from 'firebase/app';
import { sendPasswordResetEmail } from 'firebase/auth';
import Spinner from '@/components/ui/Spinner';
import { asset } from '@/lib/assets';
import { backToLogin, firebaseAuth, firebaseMessage } from '@/lib/firebase';

export default function ForgotPasswordPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sentTo, setSentTo] = useState(''); // set = the "check your email" message shows

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get('email') || '').trim();
    setBusy(true);
    setError('');
    try {
      await sendPasswordResetEmail(firebaseAuth(), email, backToLogin());
      setSentTo(email);
    } catch (err) {
      // "No such account" gets the same answer as a real one: nobody learns which emails exist
      if (err instanceof FirebaseError && err.code === 'auth/user-not-found') setSentTo(email);
      else setError(firebaseMessage(err, 'Could not send the email. Please try again.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink p-4">
      <div className="w-full max-w-md space-y-6">
        <Link href="/" className="flex justify-center">
          <Image src={asset('/images/kjs/logo/Kjs.png')} alt="KJS India" width={160} height={36} className="h-9 w-auto" />
        </Link>
        <div className="card space-y-5 p-6">
          <div>
            <h1 className="text-xl font-bold">Forgot password</h1>
            <p className="text-sm text-slate-500">We&apos;ll email you a link to set a new password.</p>
          </div>
          {sentTo ? (
            <div role="status" className="space-y-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">
              <p className="font-semibold">Check your email</p>
              <p>
                If <span className="font-semibold">{sentTo}</span> has a staff account, a link to set a new password is
                on its way. After that, log in with the new password.
              </p>
              <p>
                Nothing after 5 minutes? Check spam, or{' '}
                <button type="button" onClick={() => setSentTo('')} className="font-semibold underline">
                  try again
                </button>
                .
              </p>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3">
              <div>
                <label className="label" htmlFor="email">Work email</label>
                <input id="email" name="email" type="email" required className="input" autoComplete="username" />
              </div>
              {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
              <button disabled={busy} aria-busy={busy} className="btn-dark w-full">
                {busy && <Spinner />}
                {busy ? 'Sending…' : 'Send reset link'}
              </button>
            </form>
          )}
          <Link href="/employee/login" className="block text-center text-sm font-semibold text-sky-700 hover:underline">
            Back to log in
          </Link>
        </div>
      </div>
    </div>
  );
}
