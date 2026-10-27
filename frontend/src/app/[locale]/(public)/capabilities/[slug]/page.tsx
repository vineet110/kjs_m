import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import EnquiryButton from '@/components/public/EnquiryButton';
import { CAPABILITIES } from '@/lib/site';

// Next 15+: params arrive as a Promise.
type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return CAPABILITIES.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const c = CAPABILITIES.find((x) => x.slug === slug);
  return c ? { title: c.title, description: c.summary } : {};
}

export default async function CapabilityPage({ params }: Props) {
  const { slug } = await params;
  const c = CAPABILITIES.find((x) => x.slug === slug);
  if (!c) notFound();

  return (
    <>
      <section className="relative overflow-hidden bg-ink text-white">
        <video className="absolute inset-0 h-full w-full object-cover opacity-30" src={c.video} autoPlay muted loop playsInline preload="metadata" />
        <div className="relative mx-auto max-w-7xl px-4 py-20">
          <p className="eyebrow text-gold">Capabilities</p>
          <h1 className="mt-3 text-4xl font-extrabold">{c.title}</h1>
          <p className="mt-3 max-w-2xl text-lg text-slate-200">{c.summary}</p>
        </div>
      </section>
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 md:grid-cols-3">
        <div className="space-y-6 md:col-span-2">
          {c.intro.map((t) => <p key={t} className="text-slate-700">{t}</p>)}
          {c.sections.map((s) => (
            <div key={s.heading} className="card p-6">
              <h2 className="mb-3 text-lg font-bold">{s.heading}</h2>
              <ul className="grid gap-2 sm:grid-cols-2">
                {s.items.map((i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700"><span className="text-gold-dark">✓</span>{i}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <aside className="space-y-4">
          <div className="card space-y-3 p-6">
            <p className="font-semibold">Discuss your project</p>
            <p className="text-sm text-slate-600">Share your format and volume; we reply within one working day.</p>
            <EnquiryButton label="Send enquiry" title={`Enquiry: ${c.title.split(':')[0]}`} />
          </div>
          <div className="card p-4">
            <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Other capabilities</p>
            {CAPABILITIES.filter((x) => x.slug !== c.slug).map((x) => (
              <Link key={x.slug} href={`/capabilities/${x.slug}`} className="block py-1 text-sm hover:text-gold-dark">{x.title.split(':')[0]}</Link>
            ))}
          </div>
        </aside>
      </div>
    </>
  );
}
