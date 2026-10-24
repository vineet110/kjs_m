'use client';
import BoardDetail from '@/components/portal/BoardDetail';

export default function Page({ params }: { params: { code: string } }) {
  return <BoardDetail code={params.code} backHref="/admin/order-boards" />;
}
