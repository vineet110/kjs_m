import { ComingSoon } from '@/components/portal/PortalShell';

export default function Page({ params }: { params: { code: string } }) {
  return <ComingSoon title={`Board ${params.code}`} phase="Phase 5" what="Step view, files and deadlines for this order board." />;
}
