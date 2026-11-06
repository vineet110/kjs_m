// Shown at once while the home page waits for the API (our database is far away, so this can take
// a few seconds): the KJS mark with a spinning ring, product packs bobbing in a wave, and shimmering
// placeholder cards, while the header's gold progress bar runs. Header and footer stay.
// Only for the home page, on purpose: pages that can be "not found" (products, categories) must not
// have a loading.tsx, or they would answer 200 instead of 404 (the page starts streaming before
// notFound() runs). Those pages get the progress bar in NavigationProgress instead.
// All motion stops for visitors who ask their system for reduced motion.
import Image from 'next/image';
import { asset } from '@/lib/assets';

const PACKS = ['pacho-chocolate-bar', 'gofrey-crispy-x2', 'lupita-duble', 'maxi-big-wafers-chocolate', 'pitaro-sandwich-biscuits'];

function Shimmer({ className = '' }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-xl bg-slate-200/60 ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/70 to-transparent motion-reduce:hidden" />
    </div>
  );
}

export default function Loading() {
  return (
    // data-loading-screen: shows the header's gold bar while this screen is on the page (globals.css)
    <div aria-busy="true" aria-live="polite" data-loading-screen>

      <div className="bg-paper">
        <div className="mx-auto max-w-7xl px-4 py-8">
          <div className="relative flex min-h-[360px] flex-col items-center justify-center overflow-hidden rounded-2xl bg-gradient-to-br from-[#FDF0D9] via-[#F8DDAE] to-[#F1C47C] px-4 py-10">
            {/* KJS mark with a spinning gold ring and a soft glow */}
            <div className="relative flex h-24 w-24 items-center justify-center">
              <span className="absolute inset-0 animate-ping rounded-full bg-gold/25 [animation-duration:2s] motion-reduce:hidden" />
              <span className="absolute inset-0 animate-spin rounded-full border-4 border-white/60 border-t-gold border-r-gold-dark [animation-duration:1.1s] motion-reduce:animate-none" />
              <Image src={asset('/images/kjs/favicon.png')} alt="" width={48} height={48} className="relative h-12 w-12 rounded-full" priority />
            </div>

            <p className="mt-6 text-lg font-bold text-ink">
              Loading our products
              <span className="inline-flex w-6 justify-start" aria-hidden="true">
                {[0, 1, 2].map((d) => (
                  <span key={d} className="animate-bounce motion-reduce:animate-none" style={{ animationDelay: `${d * 150}ms` }}>.</span>
                ))}
              </span>
            </p>
            <p className="mt-1 text-sm text-slate-700">Chocolate bars, wafers, marshmallow and biscuits, made in Hyderabad</p>

            {/* Product packs bobbing in a wave */}
            <div className="mt-8 flex items-end justify-center gap-3 sm:gap-5">
              {PACKS.map((slug, k) => (
                <div
                  key={slug}
                  className={`animate-float motion-reduce:animate-none ${k === 0 || k === PACKS.length - 1 ? 'hidden sm:block' : ''}`}
                  style={{ animationDelay: `${k * 180}ms` }}
                >
                  <Image
                    src={asset(`/images/products/${slug}.jpg`)}
                    alt=""
                    width={120}
                    height={90}
                    className="w-20 rounded-xl shadow-lg ring-1 ring-black/5 sm:w-28"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Shimmering placeholder cards */}
      <div className="mx-auto max-w-7xl px-4 pb-14 pt-4">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="card overflow-hidden">
              <Shimmer className="aspect-[4/3] !rounded-none" />
              <div className="space-y-2 p-4">
                <Shimmer className="h-3 w-20" />
                <Shimmer className="h-4 w-36" />
                <Shimmer className="h-8 w-full" />
              </div>
            </div>
          ))}
        </div>
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  );
}
