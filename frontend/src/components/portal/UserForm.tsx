'use client';
// User Creation Form (admin): the form on the left, the profile card on the right filling in as you type.
// Also used to edit someone (same form, email fixed). A new account is active at once: the admin gets a
// one-time password to pass on, and the person changes it on their Profile page.
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure, type StaffUser } from '@/lib/api';
import { useMe } from './PortalShell';
import UserCard, { uploadPhoto, usePhoto } from './UserCard';
import { Msg } from './ui';

const BRANCHES = ['Main Branch']; // suggestions only: any branch name can be typed (KJS to send the real list)

export default function UserForm({ user }: { user?: StaffUser }) {
  const me = useMe();
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [v, setV] = useState({
    name: user?.name ?? '', email: user?.email ?? '', phone: user?.phone ?? '', employee_code: user?.employee_code ?? '',
    branch: user?.branch ?? '', role: user?.role ?? '', reporting_to: user?.reporting_to ? String(user.reporting_to) : '',
  });
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const saved = usePhoto(user?.id ?? null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [created, setCreated] = useState<{ name: string; email: string; password: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<StaffUser[]>('/admin/users?status=active').then(setStaff).catch(() => setStaff([]));
  }, []);
  // The picked photo shows in the card before it is uploaded
  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setV({ ...v, [k]: e.target.value });
  const boss = staff.find((s) => String(s.id) === v.reporting_to)?.name ?? '';

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // PhoneInput keeps its own state: read the composed number from the form
    const phone = String(new FormData(e.currentTarget).get('phone') ?? '');
    const body = { name: v.name, phone, employee_code: v.employee_code, branch: v.branch, role: v.role, reporting_to: v.reporting_to ? Number(v.reporting_to) : null };
    setBusy(true);
    setMsg(null);
    try {
      let id = user?.id;
      if (user) {
        await api(`/admin/users/${user.id}`, { method: 'PATCH', body });
      } else {
        const r = await api<{ user: StaffUser; temp_password: string }>('/admin/users', { method: 'POST', body: { ...body, email: v.email } });
        id = r.user.id;
        setCreated({ name: r.user.name, email: r.user.email, password: r.temp_password });
      }
      if (file && id) {
        try {
          await uploadPhoto(id, file);
        } catch (err) {
          setMsg({ ok: false, text: `Saved, but the photo did not upload: ${err instanceof ApiFailure ? err.message : 'try again'}.` });
          return;
        }
      }
      if (user) setMsg({ ok: true, text: 'Saved.' });
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save.' });
    } finally {
      setBusy(false);
    }
  }

  if (created) {
    return (
      <div className="card max-w-xl space-y-3 p-6">
        <h2 className="text-lg font-semibold">{created.name} can log in now</h2>
        <p className="text-sm text-slate-600">Give them this one-time password. It is shown only once; they change it on their Profile page.</p>
        <dl className="grid grid-cols-[8rem_1fr] gap-y-1 rounded-lg bg-slate-50 p-3 text-sm">
          <dt className="text-slate-500">Email</dt><dd className="font-mono">{created.email}</dd>
          <dt className="text-slate-500">Password</dt><dd className="select-all font-mono font-semibold">{created.password}</dd>
        </dl>
        <Msg msg={msg} />
        <div className="flex gap-2">
          <Link href="/admin/users" className="btn-dark">Back to users</Link>
          <button type="button" onClick={() => window.location.reload()} className="btn-ghost">Create another</button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <form onSubmit={submit} className="card space-y-4 p-6 shadow-lg">
        <h2 className="text-xl font-semibold">{user ? 'Edit User' : 'User Create Form'}</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div><label className="label" htmlFor="u-name">Name<Star /></label><input id="u-name" value={v.name} onChange={set('name')} required minLength={2} maxLength={100} placeholder="Enter Name" className="input" /></div>
          <div><label className="label" htmlFor="u-email">Email<Star /></label><input id="u-email" type="email" value={v.email} onChange={set('email')} required disabled={!!user} maxLength={255} placeholder="Enter Email" className="input disabled:bg-slate-50" /></div>
          {/* PhoneInput keeps its own state and puts "+91 98480 …" in a hidden input. After each key, read
              that input once React has drawn it, so the card shows the number with its code. */}
          <div onInput={(e) => {
            const box = e.currentTarget;
            requestAnimationFrame(() => setV((x) => ({ ...x, phone: box.querySelector<HTMLInputElement>('input[name="phone"]')?.value ?? x.phone })));
          }}>
            <label className="label" htmlFor="u-phone">Phone Number<Star /></label><PhoneInput id="u-phone" defaultValue={user?.phone ?? ''} maxLength={20} placeholder="Phone number" />
          </div>
          <div><label className="label" htmlFor="u-code">Employee Code<Star /></label><input id="u-code" value={v.employee_code} onChange={set('employee_code')} required maxLength={40} placeholder="Enter Employee Code" className="input" /></div>
          <div>
            <label className="label" htmlFor="u-branch">Branch<Star /></label>
            <input id="u-branch" list="branches" value={v.branch} onChange={set('branch')} required maxLength={80} placeholder="Select an Option" className="input" />
            <datalist id="branches">{BRANCHES.map((b) => <option key={b} value={b} />)}</datalist>
          </div>
          <div>
            <label className="label" htmlFor="u-role">Role<Star /></label>
            <select id="u-role" value={v.role} onChange={set('role')} required className="input">
              <option value="">Select an Option</option>
              <option value="employee">Employee</option>
              {/* Only an admin can make another admin (the server checks this too) */}
              {me.role === 'admin' && <option value="admin">Admin</option>}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="u-boss">Reporting To</label>
            {/* Empty = top of the chain (e.g. the top admin reports to no one) */}
            <select id="u-boss" value={v.reporting_to} onChange={set('reporting_to')} className="input">
              <option value="">No one (top of the chain)</option>
              {staff.filter((s) => s.id !== user?.id).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="u-photo">Profile Image</label>
            <input id="u-photo" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="input py-1.5 text-sm" />
          </div>
        </div>
        <Msg msg={msg} />
        <div className="flex justify-end gap-2">
          <Link href="/admin/users" className="btn-ghost">Cancel</Link>
          <button disabled={busy} className="btn-dark">{busy ? 'Saving…' : 'Submit'}</button>
        </div>
      </form>
      <UserCard v={{ ...v, reporting_to: boss }} photo={preview ?? saved} />
    </div>
  );
}

function Star() {
  return <span className="text-red-500" aria-hidden="true">*</span>;
}
