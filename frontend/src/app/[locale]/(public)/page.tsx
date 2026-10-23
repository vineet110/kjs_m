// P1: Home. Server-rendered so Google sees everything. All data comes from the API.
import Image from 'next/image';
import Link from 'next/link';
import CategoryGrid from '@/components/public/CategoryGrid';
import EnquiryButton from '@/components/public/EnquiryButton';
import ProductCard from '@/components/public/ProductCard';
import { serverGet, type Category, type Product } from '@/lib/api';
import { CAPABILITIES, SITE } from '@/lib/site';

export default async function HomePage() {
  const [categories, bestSellers] = await Promise.all([
    serverGet<Category[]>('/public/categories'),
    serverGet<Product[]>('/public/products?best_sellers=true'),
  ]);

  return (
    <>
      <section className="relative overflow-hidden bg-ink text-white">
        <video
          className="absolute inset-0 h-full w-full object-cover opacity-35"
          src="/images/kjs/video/banner-video.mp4"
          poster="/images/kjs/bg/banner-1.jpg"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
        />
        <div className="relative mx-auto max-w-7xl px-4 py-24 md:py-32">
          <p className="eyebrow text-gold">Co-manufacturing · Hyderabad, India</p>
          <h1 className="mt-4 max-w-3xl text-4xl font-extrabold leading-tight md:text-6xl">{SITE.tagline}</h1>
          <p className="mt-5 max-w-2xl text-lg text-slate-200">
            Coffee, tea, health drinks and confectionery, blended and packed for your brand. Trusted by global
            leaders like {SITE.trustedBy.join(', ')}.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/products" className="btn-gold">
              Explore products →
            </Link>
            <EnquiryButton
              label="Request a quote"
              className="btn border border-white/40 text-white hover:bg-white/10"
              title="Request a quote"
            />
          </div>
          <div className="mt-8 flex flex-wrap gap-2">
            {CAPABILITIES.map((c) => (
              <Link
                key={c.slug}
                href={`/capabilities/${c.slug}`}
                className="rounded-full border border-white/20 px-3 py-1 text-xs text-slate-200 hover:border-gold hover:text-gold"
              >
                {c.title.split(':')[0]}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-8 px-4 py-6">
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Certified</span>
          {SITE.certifications.map((c) => (
            <Image key={c.name} src={c.img} alt={c.name} width={90} height={50} className="h-12 w-auto object-contain" />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl space-y-6 px-4 py-16">
        <div>
          <p className="eyebrow">Our product range</p>
          <h2 className="mt-2 text-3xl font-bold">Made and packed in our factory</h2>
          <p className="mt-2 text-slate-600">
            Stick packs, sachets, pouches, cartons, jars and bulk. Private label for your brand.
          </p>
        </div>
        <CategoryGrid categories={categories ?? []} />
      </section>

      {bestSellers && bestSellers.length > 0 && (
        <section className="mx-auto max-w-7xl space-y-6 px-4 pb-16">
          <h2 className="text-2xl font-bold">Best sellers</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {bestSellers.map((p) => (
              <ProductCard key={p.id} p={p} />
            ))}
          </div>
        </section>
      )}

      <section className="bg-white py-16">
        <div className="mx-auto max-w-7xl space-y-6 px-4">
          <div>
            <p className="eyebrow">What we do</p>
            <h2 className="mt-2 text-3xl font-bold">One partner from blend to pallet</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
            {CAPABILITIES.map((c) => (
              <Link key={c.slug} href={`/capabilities/${c.slug}`} className="card p-5 hover:border-gold">
                <h3 className="font-semibold">{c.title.split(':')[0]}</h3>
                <p className="mt-2 text-sm text-slate-600">{c.summary}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16">
        <div className="flex flex-col items-start justify-between gap-6 rounded-2xl bg-forest p-8 text-white md:flex-row md:items-center">
          <div>
            <h2 className="text-2xl font-bold">Launching a product or scaling a SKU?</h2>
            <p className="mt-1 text-emerald-100">Tell us the format and volume. Our team replies within one working day.</p>
          </div>
          <div className="flex gap-3">
            <EnquiryButton label="Send enquiry" title="Send us your enquiry" />
            <a href={SITE.whatsapp} target="_blank" rel="noopener" className="btn border border-white/40 text-white hover:bg-white/10">
              WhatsApp
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
