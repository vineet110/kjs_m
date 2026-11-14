'use client';
// User Creation Form (admin): the form on the left, the profile card on the right filling in as you type.
// Also used to edit someone (same form, email fixed). A new account is active at once: the admin gets a
// one-time password to pass on, and the person changes it on their Profile page.
// Department (stored as `branch`), a job title from the list (an admin can add one right here), "Admin access"
// (only an admin sees it; everyone else is an employee whose permissions decide what they may do), and
// Reporting To, searchable by name or employee code.
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure, type StaffUser } from '@/lib/api';
import PersonPicker from './PersonPicker';
import { useMe } from './PortalShell';
import UserCard, { uploadPhoto, usePhoto } from './UserCard';
import { Msg } from './ui';
import LoadError from '@/components/ui/LoadError';
import Spinner from '@/components/ui/Spinner';

const DEPARTMENTS = ['Main Branch']; // suggestions only: any department can be typed (KJS to send the real list)
const ADD_TITLE = '__add__';

/** onSaved: after an edit is saved, with the account as the server now has it (the edit page uses it to show
 *  or hide the Permissions box at once when Admin access changed). */
export default function UserForm({ user, onSaved }: { user?: StaffUser; onSaved?: (u: StaffUser) => void }) {
  const me = useMe();
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [v, setV] = useState({
    name: user?.name ?? '', email: user?.email ?? '', phone: user?.phone ?? '', employee_code: user?.employee_code ?? '',
    branch: user?.branch ?? '', role: user?.role ?? 'employee', job_title: user?.job_title ?? '',
    reporting_to: user?.reporting_to ? String(user.reporting_to) : '',
  });
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const saved = usePhoto(user?.id ?? null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [created, setCreated] = useState<{ name: string; email: string; password: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [titles, setTitles] = useState<string[]>([]);
  const [newTitle, setNewTitle] = useState<string | null>(null); // typing a new job title (admin)
  const [titleErr, setTitleErr] = useState('');
  const [addingTitle, setAddingTitle] = useState(false);

  const [staffErr, setStaffErr] = useState<unknown>(null);
  // The "Reporting to" list. If it fails the saved choice is kept (the form state holds it), but say so.
  const loadStaff = useCallback(() => {
    setStaffErr(null);
    api<StaffUser[]>('/admin/users?status=active').then(setStaff).catch(setStaffErr);
  }, []);
  useEffect(() => {
    loadStaff();
  }, [loadStaff]);
  useEffect(() => {
    api<string[]>('/admin/job-titles').then(setTitles).catch(() => setTitleErr('Could not load the job titles.'));
  }, []);

  // A new job title: saved to the list at once (admin only) and picked for this person
  // While a new title is saving, Add / Cancel / Submit wait for it: the person is never saved with the old title
  // while the new one is still on its way (CodeRabbit on #76)
  async function addTitle() {
    if (addingTitle) return;
    const name = (newTitle ?? '').trim();
    if (name.length < 2) return setTitleErr('A job title needs at least 2 characters.');
    setTitleErr('');
    setAddingTitle(true);
    try {
      const r = await api<{ name: string }>('/admin/job-titles', { method: 'POST', body: { name } });
      setTitles((t) => (t.includes(r.name) ? t : [...t, r.name].sort((a, b) => a.localeCompare(b))));
      setV((x) => ({ ...x, job_title: r.name }));
      setNewTitle(null);
    } catch (err) {
      setTitleErr(err instanceof ApiFailure ? err.message : 'Could not add the job title.');
    } finally {
      setAddingTitle(false);
    }
  }

  function setAdmin(on: boolean) {
    // Admin = every permission and every admin page: ask first
    if (on && !confirm(`Give ${v.name || 'this person'} admin access? An admin can do everything, including managing other staff.`)) return;
    setV((x) => ({ ...x, role: on ? 'admin' : 'employee' }));
  }
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
    if (addingTitle) return;
    // PhoneInput keeps its own state: read the composed number from the form
    const phone = String(new FormData(e.currentTarget).get('phone') ?? '');
    const body = { name: v.name, phone, employee_code: v.employee_code, branch: v.branch, role: v.role, job_title: v.job_title,
      reporting_to: v.reporting_to ? Number(v.reporting_to) : null };
    setBusy(true);
    setMsg(null);
    try {
      let id = user?.id;
      if (user) {
        // Save first, then tell the page: inside onSaved?.(…) the save would be skipped without a callback
        const saved = await api<StaffUser>(`/admin/users/${user.id}`, { method: 'PATCH', body });
        onSaved?.(saved);
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
        <p className="text-sm text-slate-600">Give them this one-time password. It is shown only once. At their first login they verify their email (we send them a link), then they change the password on their Profile page.</p>
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
            <label className="label" htmlFor="u-branch">Department<Star /></label>
            <input id="u-branch" list="departments" value={v.branch} onChange={set('branch')} required maxLength={80} placeholder="Select or type a department" className="input" />
            <datalist id="departments">{DEPARTMENTS.map((b) => <option key={b} value={b} />)}</datalist>
          </div>
          <div>
            <label className="label" htmlFor="u-title">Job title</label>
            {newTitle === null ? (
              <select id="u-title" value={v.job_title}
                onChange={(e) => (e.target.value === ADD_TITLE ? setNewTitle('') : setV({ ...v, job_title: e.target.value }))} className="input">
                <option value="">No job title</option>
                {/* A saved title that is no longer in the list still shows */}
                {v.job_title && !titles.includes(v.job_title) && <option value={v.job_title}>{v.job_title}</option>}
                {titles.map((t) => <option key={t} value={t}>{t}</option>)}
                {me.role === 'admin' && <option value={ADD_TITLE}>+ Add new title…</option>}
              </select>
            ) : (
              <div className="flex gap-1">
                <input id="u-title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} maxLength={60} autoFocus
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTitle(); } }}
                  placeholder="e.g. Sales Executive" className="input" />
                <button type="button" onClick={addTitle} disabled={addingTitle} className="btn-dark px-3 disabled:opacity-50">{addingTitle ? 'Adding…' : 'Add'}</button>
                <button type="button" disabled={addingTitle} onClick={() => { setNewTitle(null); setTitleErr(''); }} className="btn-ghost px-2" aria-label="Cancel new title">✕</button>
              </div>
            )}
            {titleErr && <p className="mt-1 text-xs text-red-700">{titleErr}</p>}
          </div>
          <div>
            <label className="label" htmlFor="u-boss">Reporting To</label>
            {/* Empty = top of the chain (e.g. the top admin reports to no one) */}
            <PersonPicker id="u-boss" people={staff.filter((s) => s.id !== user?.id)} value={v.reporting_to}
              onChange={(id) => setV((x) => ({ ...x, reporting_to: id }))} emptyLabel="No one (top of the chain)" />
          </div>
          <div>
            <label className="label" htmlFor="u-photo">Profile Image</label>
            <input id="u-photo" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="input py-1.5 text-sm" />
          </div>
        </div>
        {me.role === 'admin' && user?.id !== me.id && (
          <label className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
            <input type="checkbox" checked={v.role === 'admin'} onChange={(e) => setAdmin(e.target.checked)} className="mt-0.5" />
            <span><span className="font-semibold">Admin access</span>: every permission and every admin page. Leave off for employees;
              what an employee may do is set with their permissions.</span>
          </label>
        )}
        {staffErr != null && <LoadError error={staffErr} onRetry={loadStaff} />}
        <Msg msg={msg} />
        <div className="flex justify-end gap-2">
          <Link href="/admin/users" className="btn-ghost">Cancel</Link>
          <button disabled={busy || addingTitle} className="btn-dark">{busy && <Spinner />}{busy ? 'Saving…' : 'Submit'}</button>
        </div>
      </form>
      <UserCard v={{ ...v, reporting_to: boss }} photo={preview ?? saved} />
    </div>
  );
}

function Star() {
  return <span className="text-red-500" aria-hidden="true">*</span>;
}
