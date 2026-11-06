import Image from 'next/image';
import { SITE } from '@/lib/site';
import { asset } from '@/lib/assets';

export default function SiteFooter() {
  return (
    <footer className="mt-20 bg-ink text-slate-300">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 md:grid-cols-3">
        <div className="space-y-3 md:col-span-2">
          <Image src={asset('/images/kjs/logo/Kjs.png')} alt="KJS India" width={140} height={32} className="h-8 w-auto" />
          <p className="max-w-md text-sm text-slate-400">
            Co-manufacturing and private label for coffee, tea, health drinks and confectionery. Since {SITE.since}.
          </p>
          <p className="text-sm text-slate-400">{SITE.address}</p>
        </div>
        <div className="space-y-2 text-sm">
          <p className="font-semibold text-white">Contact</p>
          <a href={`tel:${SITE.phone.replace(/\s/g, '')}`} className="block hover:text-gold">{SITE.phone}</a>
          <a href={`mailto:${SITE.email}`} className="block hover:text-gold">{SITE.email}</a>
          <a href={SITE.whatsapp} target="_blank" rel="noopener" className="block hover:text-gold">WhatsApp</a>
          <a href={`mailto:${SITE.careers}`} className="block hover:text-gold">Careers</a>
        </div>
      </div>
      <div className="border-t border-white/10 py-4 text-center text-xs text-slate-500">
        © {new Date().getFullYear()} KJS India Pvt. Ltd. All rights reserved.
      </div>
    </footer>
  );
}
