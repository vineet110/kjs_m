'use client';
// My activity: the same view admins see on Team work, for my own data only (the server uses my login,
// never an id from the page).
import { PageTitle } from '@/components/portal/ui';
import WorkView from '@/components/portal/WorkView';

export default function MyWork() {
  return (
    <div className="space-y-6">
      <PageTitle title="My activity" sub="Your calls, emails, notes, tasks, chat and attendance. Only you and people allowed to see Team work can see this." />
      <WorkView base="/work/me" />
    </div>
  );
}
