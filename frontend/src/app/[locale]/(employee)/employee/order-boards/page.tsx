'use client';
// Order boards I am a member of.
import { useEffect, useState } from 'react';
import { BoardList } from '@/components/portal/BoardDetail';
import { PageTitle } from '@/components/portal/ui';
import { api, type BoardSummary } from '@/lib/api';

export default function MyBoards() {
  const [boards, setBoards] = useState<BoardSummary[] | null>(null);
  useEffect(() => {
    api<BoardSummary[]>('/boards').then(setBoards).catch(() => setBoards([]));
  }, []);
  return (
    <div className="space-y-6">
      <PageTitle title="My order boards" sub="Boards where you are on at least one step." />
      {boards === null ? <p className="text-sm text-slate-500">Loading…</p> : <BoardList base="/employee/order-boards" boards={boards} />}
    </div>
  );
}
