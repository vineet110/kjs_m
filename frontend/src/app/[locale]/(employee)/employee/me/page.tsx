'use client';
// Profile: my details, notification settings, password.
import { useEffect, useState } from 'react';
import { Msg, PageTitle } from '@/components/portal/ui';
import { api, ApiFailure } from '@/lib/api';

type Profile = { id: number; name: string; email: string; phone: string; role: string; categories: string[]; notify_email: boolean; notify_whatsapp: boolean };

export default function ProfilePage() {
  const [p, setP] = useState<Profile | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    api<Profile>('/auth/profile').then(setP);
  }, []);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      setP(await api<Profile>('/auth/profile', {
        method: 'PATCH',
        body: { name: f.get('name'), phone: f.get('phone'), notify_email: f.get('notify_email') === 'on', notify_whatsapp: f.get('notify_whatsapp') === 'on' },
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
    try {
      await api('/auth/password', { method: 'POST', body: { current: f.current, new: f.new } });
      setPwMsg({ ok: true, text: 'Password changed. Other browsers where you were logged in are logged out.' });
      form.reset();
    } catch (err) {
      setPwMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not change.' });
    }
  }

  if (!p) return <p className="text-sm text-slate-500">Loading…</p>;
  return (
    <div className="max-w-2xl space-y-6">
      <PageTitle title="Profile" sub={`${p.email} · ${p.role}${p.categories.length ? ` · categories: ${p.categories.join(', ')}` : ''}`} />
      <form onSubmit={save} className="card space-y-3 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label className="label">Name</label><input name="name" defaultValue={p.name} required minLength={2} className="input" /></div>
          <div><label className="label">Phone / WhatsApp</label><input name="phone" defaultValue={p.phone} maxLength={20} className="input" /></div>
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
  );
}
