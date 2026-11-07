'use client';
// The profile card from the User Creation Form: photo, name, then email / phone / employee code / branch /
// role / reporting to. The admin's form shows it live while typing; the Profile page shows the saved one.
// Photos are files owned by ("user", id); the newest one is the photo.
import { useEffect, useState } from 'react';
import { api, upload, type StoredFile } from '@/lib/api';
import { Icon } from './icons';

export type CardValues = {
  name: string; email: string; phone: string; employee_code: string; branch: string; role: string; reporting_to: string;
};

/** The photo's address (or null) for a user; `version` re-asks after a new upload. */
export function usePhoto(userId: number | null, version = 0) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (!userId) return setSrc(null);
    api<StoredFile[]>(`/files?owner_type=user&owner_id=${userId}`)
      .then((fs) => {
        const photo = fs.filter((f) => f.content_type.startsWith('image/') && f.delete_status !== 'approved').sort((a, b) => b.id - a.id)[0];
        setSrc(photo ? `/api/v1/files/${photo.id}/download` : null);
      })
      .catch(() => setSrc(null));
  }, [userId, version]);
  return src;
}

export async function uploadPhoto(userId: number, file: File) {
  const form = new FormData();
  form.append('owner_type', 'user');
  form.append('owner_id', String(userId));
  form.append('file', file);
  await upload('/files', form);
}

export default function UserCard({ v, photo }: { v: CardValues; photo: string | null }) {
  const items: [string, string][] = [
    ['Email', v.email || 'abc@kjsindia.com'],
    ['Phone Number', v.phone || '+91'],
    ['Employee Code', v.employee_code || 'Employee Code'],
    ['Branch', v.branch || 'Branch'],
    ['Role', v.role ? v.role.charAt(0).toUpperCase() + v.role.slice(1) : 'Role'],
    ['Reporting To', v.reporting_to || 'Report To'],
  ];
  return (
    <div className="card overflow-hidden p-4 shadow-lg">
      <div className="flex flex-col items-center gap-4 rounded-xl bg-gradient-to-br from-indigo-50 via-white to-fuchsia-50 px-4 pb-6 pt-6">
        <span className="flex h-32 w-32 items-center justify-center overflow-hidden rounded-full border-4 border-white bg-slate-100 shadow">
          {/* eslint-disable-next-line @next/next/no-img-element -- a staff-only file behind the login; next/image can't fetch it */}
          {photo ? <img src={photo} alt="" className="h-full w-full object-cover" /> : <Icon name="user" className="h-20 w-20 text-slate-700" />}
        </span>
        <p className="text-lg font-semibold uppercase tracking-wide">{v.name || 'User name'}</p>
      </div>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        {items.map(([k, val]) => (
          <div key={k} className="rounded-lg bg-gradient-to-br from-indigo-50/60 to-fuchsia-50/40 p-3">
            <dt className="text-sm font-medium text-slate-800">{k}</dt>
            <dd className="truncate text-sm text-slate-500">{val}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
