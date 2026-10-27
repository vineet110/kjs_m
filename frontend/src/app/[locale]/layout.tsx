import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import '@/app/globals.css';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages } from 'next-intl/server';
import { notFound } from 'next/navigation';

const LOCALES = ['en']; // keep in sync with src/proxy.ts

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: { default: 'KJS India | Contract Manufacturing: Coffee, Tea, Health Drinks, Confectionery', template: '%s | KJS India' },
  description:
    'KJS India is a private-label and contract manufacturer in Hyderabad: stick packs, blending, packaging and warehousing for brands, distributors and importers.',
  icons: { icon: '/images/kjs/favicon.png' },
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
    <html lang={locale}>
      <body className={`${inter.className} bg-paper text-slate-900 antialiased`}>
        <NextIntlClientProvider messages={messages}>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
