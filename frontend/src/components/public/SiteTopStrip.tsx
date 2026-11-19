// Thin strip above the website header (site_ui.ini top_strip): since when, certificates, phone, email.
// Not sticky: it scrolls away and the header stays. Phones show only the first item.
import { SITE } from '@/lib/site';

export default function SiteTopStrip() {
  const certs = SITE.certifications.filter((c) => c.name !== 'Sodexo').map((c) => c.name).join(' · ');
  return (
    <div className="border-b border-white/10 bg-ink text-xs text-slate-400">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-1.5">
        <p className="flex flex-wrap gap-x-6">
          <span><b className="font-semibold text-gold">Since {SITE.since}</b> · Co-manufacturing in Hyderabad, India</span>
          <span className="hidden md:inline">{certs}</span>
        </p>
        <p className="hidden gap-x-6 sm:flex">
          <span>{SITE.phone}</span>
          <span>{SITE.email}</span>
        </p>
      </div>
    </div>
  );
}
