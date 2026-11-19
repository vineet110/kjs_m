import ConnectPopup from '@/components/public/ConnectPopup';
import HoverGrowSides from '@/components/public/HoverGrowSides';
import { JsonLd, organizationLd } from '@/components/public/JsonLd';
import KokoChatWidget from '@/components/public/KokoChatWidget';
import OffersTicker from '@/components/public/OffersTicker';
import SiteFooter from '@/components/public/SiteFooter';
import SiteHeader from '@/components/public/SiteHeader';
import SiteTopStrip from '@/components/public/SiteTopStrip';
import SiteTracker from '@/components/public/SiteTracker';
import { themeScript } from '@/lib/theme';
import WhatsAppButton from '@/components/public/WhatsAppButton';
import OfferDock from '@/components/public/talk/OfferDock';
import TalkBubble from '@/components/public/talk/TalkBubble';
import { features, insightsConfig, serverGet, siteUi, texts, type Category } from '@/lib/api';
import { rangeText } from '@/lib/catalogue';

export default async function PublicLayout({ children }: { children: React.ReactNode }) {
  // on/off switches from config/features.ini; the categories shown (Admin > Products) for the range in words;
  // the Website insights tracker settings (config/site_insights.ini)
  const [f, categories, insights, ui, t] = await Promise.all([
    features(), serverGet<Category[]>('/public/categories').catch(() => null), insightsConfig(), siteUi(), texts(),
  ]);
  // The site talks (site_ui.ini talk, offer_box): only the talk.* and offer.* texts go to the browser
  const talkTexts = Object.fromEntries(Object.entries(t).filter(([k]) => k.startsWith('talk.') || k.startsWith('offer.')));
  const range = rangeText(categories);
  // Soft pulsing ring around the Ask Koko and WhatsApp buttons (config/site_ui.ini)
  const glow = ui.enabled && ui.glow ? ui.glow_seconds : null;
  // ☀/☾ dark website (site_ui.ini theme_toggle). Off: the site is always light, whatever was chosen before.
  const themed = ui.enabled && ui.theme_toggle;
  return (
    // site-shell: the website's own box. Dark-mode colours (globals.css) apply only inside it, never to the portal.
    <div className="site-shell min-h-screen">
      {/* Before anything paints: the remembered theme, so a dark-mode visitor never sees a white flash */}
      <script dangerouslySetInnerHTML={{ __html: themed ? themeScript(ui.dark_follows_system) : "document.documentElement.classList.remove('dark')" }} />
      <JsonLd data={organizationLd(range)} />
      {ui.enabled && ui.top_strip && <SiteTopStrip />}
      {f.offers_ticker && <OffersTicker />}
      <SiteHeader showPartners={f.partners} showPrivateLabel theme={themed ? { followSystem: ui.dark_follows_system } : null} />
      <main className="site-public min-h-[60vh]">{children}</main>
      <SiteFooter range={range} />
      <HoverGrowSides />
      {f.whatsapp_button && <WhatsAppButton glowSeconds={glow} />}
      {f.koko && <KokoChatWidget glowSeconds={glow} />}
      {/* On unless switched off (an older API without the switch still shows it) */}
      {f.connect_popup !== false && <ConnectPopup />}
      <SiteTracker config={insights} />
      <TalkBubble texts={talkTexts} ui={ui} />
      <OfferDock texts={talkTexts} ui={ui} />
    </div>
  );
}
