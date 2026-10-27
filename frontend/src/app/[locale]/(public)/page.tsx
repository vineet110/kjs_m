// P1: Home, laid out like a B2B marketplace: search, category menu, banner, product range with
// quick view and an enquiry list. Server-rendered so Google sees everything. All data comes from the API.
import Image from 'next/image';
import Link from 'next/link';
import EnquiryButton from '@/components/public/EnquiryButton';
import CategoryMenu from '@/components/public/home/CategoryMenu';
import HeroCarousel, { type Slide } from '@/components/public/home/HeroCarousel';
import HomeSearch from '@/components/public/home/HomeSearch';
import ProductExplorer from '@/components/public/home/ProductExplorer';
import type { Metadata } from 'next';
import { serverGet, texts, type Category, type Product } from '@/lib/api';
import { imageOf, parseItems } from '@/lib/catalogue';
import { CAPABILITIES, SITE } from '@/lib/site';

// Title, description and headline are editable in Admin > Website (defaults in content_service.py).
export async function generateMetadata(): Promise<Metadata> {
  const t = await texts();
  return { title: { absolute: t['seo.home.title'] ?? 'KJS India' }, description: t['seo.home.description'] };
}

const POPULAR = ['gofrey-crispy-x2', 'pacho-mellow', 'petit-beurre-biscuits', 'maxi-cream-wafers', 'wafer-time'];

const STEPS = [
  { title: 'Send your requirement', text: 'Product, pack size, volume and destination. One form, or the enquiry list.' },
  { title: 'Get quote and samples', text: 'Our sales team replies within one working day with prices and samples.' },
  { title: 'Approve your pack', text: 'Our recipe in your brand and design, or our own KJS India brands.' },
  { title: 'Production and dispatch', text: 'Made in our Hyderabad factory under ISO and FSSC 22000 quality systems.' },
];

export default async function HomePage() {
  const [categories, productList, t] = await Promise.all([
    serverGet<Category[]>('/public/categories'),
    serverGet<Product[]>('/public/products'),
    texts(),
  ]);
  const cats = categories ?? [];
  const products = productList ?? [];
  const itemCount = products.reduce((n, p) => n + parseItems(p.description).length, 0);

  // Pictures for the banner: chosen products if they exist, else any products with a picture
  const withImage = products.filter(imageOf);
  const pick = (slugs: string[]) => {
    const chosen = slugs.map((s) => withImage.find((p) => p.slug === s)).filter((p): p is Product => !!p);
    return (chosen.length ? chosen : withImage.slice(0, 3)).map((p) => imageOf(p)!);
  };
  const slides: Slide[] = [
    {
      eyebrow: 'Confectionery co-manufacturing',
      title: 'Chocolate bars, wafers and biscuits for your brand',
      text: products.length
        ? `${products.length} product families and ${itemCount} items, made and packed in Hyderabad for retailers, distributors and importers.`
        : 'Made and packed in Hyderabad for retailers, distributors and importers.',
      href: '#range',
      cta: 'Explore the range',
      images: pick(['gofrey-crispy-x2', 'pacho-chocolate-bar', 'bigy-mellow']),
      tone: 'from-[#FDF0D9] via-[#F8DDAE] to-[#F1C47C]',
    },
    {
      eyebrow: 'Private label',
      title: 'Your brand on our proven recipes',
      text: `Pick a product, choose the pack and weight, and launch faster with the co-manufacturer trusted by ${SITE.trustedBy.join(', ')}.`,
      href: '/private-label',
      cta: 'Build your private label',
      images: pick(['maxi-big-wafers-chocolate', 'lupita-duble', 'peti-latte-2in1']),
      tone: 'from-[#EEF5EF] via-[#D9EADC] to-[#B7D5BE]',
    },
    {
      eyebrow: 'Two factories · Hyderabad',
      title: t['home.hero_title'] ?? SITE.tagline,
      text: t['home.hero_text'] ?? 'Two modern manufacturing units that can make more than 250 products, with high-speed lines and strict quality control.',
      href: '/capabilities/stick-pack-factory',
      cta: 'See our capabilities',
      images: pick(['pitaro-sandwich-biscuits', 'wafer-time', 'extreme4-dark']),
      tone: 'from-[#FBEDEA] via-[#F4D3CD] to-[#E9B4AB]',
    },
  ];

  const popular = POPULAR.map((s) => products.find((p) => p.slug === s)).filter((p): p is Product => !!p);
  const stocked = cats.filter((c) => c.product_count > 0);
  const onRequest = cats.filter((c) => c.product_count === 0);

  return (
    <>
      <h1 className="sr-only">KJS India: {t['home.hero_title'] ?? SITE.tagline}</h1>

      {/* Search band */}
      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-5">
          <div className="grid items-center gap-3 md:grid-cols-[1fr_auto]">
            <HomeSearch products={products} categories={cats} />
            <EnquiryButton label="Request for quotation" source="quote" title="Request for quotation" className="btn-dark rounded-full !py-3" />
          </div>
          {popular.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <span className="text-slate-500">Popular:</span>
              {popular.map((p) => (
                <Link key={p.slug} href={`/products/${p.slug}`} className="rounded-full bg-paper px-3 py-1 text-slate-700 hover:bg-gold-light/50">
                  {p.name}
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Category menu · banner · buyer panel */}
      <section className="bg-paper">
        <div className="mx-auto grid max-w-7xl gap-4 px-4 py-5 lg:h-[420px] lg:grid-cols-[230px_1fr_250px]">
          <CategoryMenu categories={cats} products={products} />
          <HeroCarousel slides={slides} />
          <aside className="hidden flex-col gap-4 lg:flex">
            <div className="card p-5">
              <p className="font-semibold">Buying for your brand or store?</p>
              <p className="mt-1 text-xs text-slate-600">Prices, samples and pack options from our sales team.</p>
              <EnquiryButton label="Request a quote" source="quote" title="Request a quote" className="btn-gold mt-4 w-full" />
              <EnquiryButton label="Request a sample" source="sample" title="Request a sample" className="btn-ghost mt-2 w-full" />
            </div>
            <div className="card flex flex-1 flex-col justify-center gap-3 bg-ink p-5 text-white">
              {[
                ['250+', 'products our two units can make'],
                [String(products.length || '50+'), 'product families in the catalogue'],
                ['0.9–3 g', 'precise stick-pack fills'],
              ].map(([big, small]) => (
                <div key={small}>
                  <p className="text-2xl font-extrabold text-gold">{big}</p>
                  <p className="text-xs text-slate-300">{small}</p>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </section>

      {/* Trust strip */}
      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-x-10 gap-y-4 px-4 py-5">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Certified</span>
            {SITE.certifications.map((c) => (
              <Image key={c.name} src={c.img} alt={c.name} width={80} height={44} className="h-10 w-auto object-contain" />
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Co-manufacturing partner to</span>
            {SITE.trustedBy.map((b) => (
              <span key={b} className="rounded-full border border-slate-200 px-3 py-1 text-sm font-semibold text-slate-700">{b}</span>
            ))}
          </div>
        </div>
      </section>

      {/* Top categories */}
      {stocked.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pt-14">
          <div className="flex items-end justify-between">
            <div>
              <p className="eyebrow">Top categories</p>
              <h2 className="mt-2 text-3xl font-bold">Shop by category</h2>
            </div>
            <Link href="/products" className="hidden text-sm font-semibold text-gold-dark hover:underline sm:block">All products →</Link>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stocked.map((c) => (
              <Link key={c.slug} href={`/categories/${c.slug}`} className="card group overflow-hidden p-3 transition-shadow hover:shadow-lg">
                <div className="grid grid-cols-2 gap-1.5">
                  {withImage.filter((p) => p.category_slug === c.slug).slice(0, 4).map((p) => (
                    <Image key={p.slug} src={imageOf(p)!} alt="" width={160} height={120} className="aspect-[4/3] w-full rounded-md object-cover transition-transform group-hover:scale-[1.03]" />
                  ))}
                </div>
                <div className="flex items-baseline justify-between px-1 pb-1 pt-3">
                  <h3 className="font-bold group-hover:text-forest">{c.name}</h3>
                  <span className="text-xs text-slate-500">{c.product_count} products</span>
                </div>
              </Link>
            ))}
          </div>
          {onRequest.length > 0 && (
            <p className="mt-4 text-sm text-slate-600">
              Also made to order:{' '}
              {onRequest.map((c, i) => (
                <span key={c.slug}>
                  <Link href={`/categories/${c.slug}`} className="font-semibold text-slate-800 hover:text-gold-dark">{c.name}</Link>
                  {i < onRequest.length - 1 ? ', ' : '.'}
                </span>
              ))}
            </p>
          )}
        </section>
      )}

      {/* Product range */}
      <section id="range" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-14">
        <div className="mb-6">
          <p className="eyebrow">Our product range</p>
          <h2 className="mt-2 text-3xl font-bold">Made and packed in our factory</h2>
          <p className="mt-2 text-slate-600">
            Open any product for its items, weights and pack sizes. Add products to your enquiry list and ask for one quote.
          </p>
        </div>
        {products.length > 0 ? (
          <ProductExplorer products={products} categories={cats} />
        ) : (
          <div className="card flex flex-col items-start gap-3 p-6">
            <p className="font-semibold">Our detailed product list is being published.</p>
            <p className="text-sm text-slate-600">Tell us what you need and we will send the catalogue and price sheet.</p>
            <EnquiryButton label="Request catalogue" source="price_sheet" title="Request our catalogue" />
          </div>
        )}
      </section>

      {/* How ordering works */}
      <section className="bg-white py-14">
        <div className="mx-auto max-w-7xl px-4">
          <p className="eyebrow">How it works</p>
          <h2 className="mt-2 text-3xl font-bold">From enquiry to dispatch in four steps</h2>
          <ol className="mt-8 grid gap-4 md:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.title} className="relative rounded-xl border border-slate-200 bg-paper p-5">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gold text-sm font-extrabold text-ink">{i + 1}</span>
                <h3 className="mt-3 font-semibold">{s.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{s.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Capabilities */}
      <section className="py-14">
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

      <section className="mx-auto max-w-7xl px-4 pb-20">
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
