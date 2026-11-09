'use client';
// Order boards I am a member of.
import { useCallback, useEffect, useState } from 'react';
import { BoardList } from '@/components/portal/BoardDetail';
import { PageTitle } from '@/components/portal/ui';
import { api, type BoardSummary } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

export default function MyBoards() {
  const [boards, setBoards] = useState<BoardSummary[] | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const load = useCallback(() => {
    setLoadErr(null);
    api<BoardSummary[]>('/boards').then(setBoards).catch(setLoadErr);
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="space-y-6">
      <PageTitle title="My order boards" sub="Boards you are on. Everyone on a board can see and update it." />
      {loadErr ? <LoadError error={loadErr} onRetry={load} /> : boards === null ? <Loading /> : <BoardList base="/employee/order-boards" boards={boards} />}
    </div>
  );
}
