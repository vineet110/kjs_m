import { JsonLd, organizationLd } from '@/components/public/JsonLd';
import { Suspense } from 'react';
import KokoChatWidget from '@/components/public/KokoChatWidget';
import NavigationProgress from '@/components/public/NavigationProgress';
import OffersTicker from '@/components/public/OffersTicker';
import SiteFooter from '@/components/public/SiteFooter';
import SiteHeader from '@/components/public/SiteHeader';
import WhatsAppButton from '@/components/public/WhatsAppButton';
import { features } from '@/lib/api';

export default async function PublicLayout({ children }: { children: React.ReactNode }) {
  const f = await features(); // on/off switches from config/features.ini
  return (
    <>
      <JsonLd data={organizationLd} />
      {f.offers_ticker && <OffersTicker />}
      <SiteHeader showPartners={f.partners} showPrivateLabel />
      {/* Suspense: it reads the URL (useSearchParams); fallback null, so pages themselves never stream */}
      <Suspense fallback={null}>
        <NavigationProgress />
      </Suspense>
      <main className="min-h-[60vh]">{children}</main>
      <SiteFooter />
      {f.whatsapp_button && <WhatsAppButton />}
      {f.koko && <KokoChatWidget />}
    </>
  );
}
