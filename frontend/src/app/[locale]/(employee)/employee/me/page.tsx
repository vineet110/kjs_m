'use client';
// Profile: my details, notification settings, password. On the right, my profile card (same look as the
// admin's User Creation Form). Employee code, branch, role and reporting to are set by the admin: shown
// here, not editable. My photo I can change myself.
import { useCallback, useEffect, useState } from 'react';
import { Msg, PageTitle } from '@/components/portal/ui';
import UserCard, { uploadPhoto, usePhoto } from '@/components/portal/UserCard';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import { firebaseAuth, firebaseMessage, leaveFirebase } from '@/lib/firebase';
import { FirebaseError } from 'firebase/app';
import { signInWithEmailAndPassword, updatePassword } from 'firebase/auth';

type Profile = {
  id: number; name: string; email: string; phone: string; role: string; categories: string[]; notify_email: boolean; notify_whatsapp: boolean;
  employee_code: string; branch: string; job_title: string; reporting_to_name: string;
};

export default function ProfilePage() {
  const [p, setP] = useState<Profile | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [photoMsg, setPhotoMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [photoVersion, setPhotoVersion] = useState(0);
  const photo = usePhoto(p?.id ?? null, photoVersion);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const load = useCallback(() => {
    setLoadErr(null);
    api<Profile>('/auth/profile').then(setP).catch(setLoadErr);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function changePhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !p) return;
    try {
      await uploadPhoto(p.id, file);
      setPhotoVersion((n) => n + 1);
      setPhotoMsg({ ok: true, text: 'Photo updated.' });
    } catch (err) {
      setPhotoMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not upload the photo.' });
    }
    e.target.value = '';
  }

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      setP(await api<Profile>('/auth/profile', {
        method: 'PATCH',
        body: {
          name: f.get('name'),
          // Only a changed phone is sent (left out = unchanged), so an older number saved before the phone
          // check can never block saving the other settings
          ...(f.get('phone') !== (p?.phone ?? '') && { phone: f.get('phone') }),
          notify_email: f.get('notify_email') === 'on', notify_whatsapp: f.get('notify_whatsapp') === 'on',
        },
      }));
      setMsg({ ok: true, text: 'Saved.' });
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save.' });
    }
  }

  async function changePassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    if (f.new !== f.repeat) return setPwMsg({ ok: false, text: 'The two new passwords are different.' });
    if (!p) return;
    // Firebase keeps the password: signing in with the current one proves it (and makes the sign-in fresh,
    // which the API asks for), then Firebase changes it. The API then logs out the other browsers.
    try {
      const { user } = await signInWithEmailAndPassword(firebaseAuth(), p.email, f.current).catch((err) => {
        throw firebaseMessage(err) === 'Email or password is wrong.' ? new Error('Your current password is wrong.') : err;
      });
      await updatePassword(user, f.new);
      const idToken = await user.getIdToken(true);
      await api('/auth/password', { method: 'POST', body: { id_token: idToken } }).finally(leaveFirebase);
      setPwMsg({ ok: true, text: 'Password changed. Other browsers where you were logged in are logged out.' });
      form.reset();
    } catch (err) {
      await leaveFirebase();
      const text = err instanceof ApiFailure ? err.message
        : err instanceof FirebaseError ? firebaseMessage(err, 'Could not change.')
        : err instanceof Error ? err.message : 'Could not change.';
      setPwMsg({ ok: false, text });
    }
  }

  if (!p) return loadErr ? <LoadError error={loadErr} onRetry={load} /> : <Loading />;
  return (
    <div className="space-y-6">
      <PageTitle title="Profile" sub={`${p.email} · ${p.role}${p.categories.length ? ` · categories: ${p.categories.join(', ')}` : ''}`} />
      <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-6">
      <form onSubmit={save} className="card space-y-3 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label className="label">Name</label><input name="name" defaultValue={p.name} required minLength={2} className="input" /></div>
          <div><label className="label" htmlFor="me-phone">Phone / WhatsApp *</label><PhoneInput id="me-phone" defaultValue={p.phone} maxLength={20} /></div>
        </div>
        <fieldset className="space-y-1 text-sm">
          <legend className="label">Notifications (the bell always shows them)</legend>
          <label className="flex items-center gap-2"><input type="checkbox" name="notify_email" defaultChecked={p.notify_email} /> Also send me an email</label>
          <label className="flex items-center gap-2"><input type="checkbox" name="notify_whatsapp" defaultChecked={p.notify_whatsapp} /> Also send me WhatsApp messages (starts after KJS&apos;s WhatsApp Business setup)</label>
        </fieldset>
        <Msg msg={msg} />
        <button className="btn-dark">Save</button>
      </form>
      <form onSubmit={changePassword} className="card space-y-3 p-5">
        <h2 className="font-semibold">Change password</h2>
        <div><label className="label">Current password</label><input type="password" name="current" required autoComplete="current-password" className="input" /></div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label className="label">New password (10+ characters)</label><input type="password" name="new" required minLength={10} autoComplete="new-password" className="input" /></div>
          <div><label className="label">New password again</label><input type="password" name="repeat" required minLength={10} autoComplete="new-password" className="input" /></div>
        </div>
        <Msg msg={pwMsg} />
        <button className="btn-dark">Change password</button>
      </form>
      </div>
      <div className="space-y-3">
        <UserCard
          v={{ name: p.name, email: p.email, phone: p.phone, employee_code: p.employee_code, branch: p.branch, job_title: p.job_title, role: p.role, reporting_to: p.reporting_to_name }}
          photo={photo}
        />
        <div className="card space-y-2 p-4 text-sm">
          <label className="label" htmlFor="me-photo">Profile Image</label>
          <input id="me-photo" type="file" accept="image/png,image/jpeg,image/webp" onChange={changePhoto} className="input py-1.5" />
          <Msg msg={photoMsg} />
          <p className="text-xs text-slate-500">Employee code, department, job title and reporting to are set by the admin. Ask them to change these.</p>
        </div>
      </div>
      </div>
    </div>
  );
}
