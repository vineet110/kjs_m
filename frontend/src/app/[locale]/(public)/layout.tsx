import ConnectPopup from '@/components/public/ConnectPopup';
import HoverGrowSides from '@/components/public/HoverGrowSides';
import { JsonLd, organizationLd } from '@/components/public/JsonLd';
import KokoChatWidget from '@/components/public/KokoChatWidget';
import OffersTicker from '@/components/public/OffersTicker';
import SiteFooter from '@/components/public/SiteFooter';
import SiteHeader from '@/components/public/SiteHeader';
import SiteTracker from '@/components/public/SiteTracker';
import WhatsAppButton from '@/components/public/WhatsAppButton';
import { features, insightsConfig, serverGet, type Category } from '@/lib/api';
import { rangeText } from '@/lib/catalogue';

export default async function PublicLayout({ children }: { children: React.ReactNode }) {
  // on/off switches from config/features.ini; the categories shown (Admin > Products) for the range in words;
  // the Website insights tracker settings (config/site_insights.ini)
  const [f, categories, insights] = await Promise.all([
    features(), serverGet<Category[]>('/public/categories').catch(() => null), insightsConfig(),
  ]);
  const range = rangeText(categories);
  return (
    <>
      <JsonLd data={organizationLd(range)} />
      {f.offers_ticker && <OffersTicker />}
      <SiteHeader showPartners={f.partners} showPrivateLabel />
      <main className="site-public min-h-[60vh]">{children}</main>
      <SiteFooter range={range} />
      <HoverGrowSides />
      {f.whatsapp_button && <WhatsAppButton />}
      {f.koko && <KokoChatWidget />}
      {/* On unless switched off (an older API without the switch still shows it) */}
      {f.connect_popup !== false && <ConnectPopup />}
      <SiteTracker config={insights} />
    </>
  );
}
