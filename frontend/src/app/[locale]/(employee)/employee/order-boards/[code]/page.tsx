'use client';
import { use } from 'react';
import BoardDetail from '@/components/portal/BoardDetail';

// Next 15+: params arrive as a Promise; use() unwraps it in a client component.
export default function Page({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  return <BoardDetail code={code} backHref="/employee/order-boards" />;
}
