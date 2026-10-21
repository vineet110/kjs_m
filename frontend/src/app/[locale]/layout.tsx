import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import '@/app/globals.css';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages } from 'next-intl/server';
import KokoChatWidget from '@/components/public/KokoChatWidget';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'KJS India Digital Platform',
  description: 'Enterprise portal and product platform for KJS India',
};

export default async function RootLayout({
  children,
  params: { locale }
}: {
  children: React.ReactNode;
  params: { locale: string };
}) {
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body className={inter.className}>
        <NextIntlClientProvider messages={messages}>
          {children}
          {/* Koko AI floating widget present across pages */}
          <KokoChatWidget />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
