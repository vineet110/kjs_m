import { JsonLd, organizationLd } from '@/components/public/JsonLd';
import KokoChatWidget from '@/components/public/KokoChatWidget';
import SiteFooter from '@/components/public/SiteFooter';
import SiteHeader from '@/components/public/SiteHeader';

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <JsonLd data={organizationLd} />
      <SiteHeader />
      <main className="min-h-[60vh]">{children}</main>
      <SiteFooter />
      <KokoChatWidget />
    </>
  );
}
