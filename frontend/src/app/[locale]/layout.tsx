import type { Metadata } from 'next';
import { Inter, Plus_Jakarta_Sans } from 'next/font/google';
import '@/app/globals.css';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages } from 'next-intl/server';
import { notFound } from 'next/navigation';
import { asset } from '@/lib/assets';

const LOCALES = ['en']; // keep in sync with src/proxy.ts

const inter = Inter({ subsets: ['latin'] });
// Headings on the public site (globals.css, .site-public). Part of Next, so no extra package.
const display = Plus_Jakarta_Sans({ subsets: ['latin'], weight: ['600', '700', '800'], variable: '--font-display' });

export const metadata: Metadata = {
  title: { default: 'KJS India | Contract Manufacturing: Coffee, Tea, Health Drinks, Confectionery', template: '%s | KJS India' },
  description:
    'KJS India is a private-label and contract manufacturer in Hyderabad: stick packs, blending, packaging and warehousing for brands, distributors and importers.',
  icons: { icon: asset('/images/kjs/favicon.png') },
};

export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>; // Next 15+: a Promise
}) {
  const { locale } = await params;
  // Without this, any first path segment (e.g. /robots.txt) would be treated as a "locale".
  if (!LOCALES.includes(locale)) notFound();
  const messages = await getMessages();
  return (
    <html lang={locale} className={display.variable}>
      <body className={`${inter.className} bg-paper text-slate-900 antialiased`}>
        <NextIntlClientProvider messages={messages}>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
