import ConnectPopup from '@/components/public/ConnectPopup';
import { JsonLd, organizationLd } from '@/components/public/JsonLd';
import KokoChatWidget from '@/components/public/KokoChatWidget';
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
      <main className="site-public min-h-[60vh]">{children}</main>
      <SiteFooter />
      {f.whatsapp_button && <WhatsAppButton />}
      {f.koko && <KokoChatWidget />}
      {/* On unless switched off (an older API without the switch still shows it) */}
      {f.connect_popup !== false && <ConnectPopup />}
    </>
  );
}
