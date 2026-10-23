// Structured data (JSON-LD) helps Google show the company name, address and products correctly.
import { SITE } from '@/lib/site';

export function JsonLd({ data }: { data: Record<string, unknown> }) {
  // JSON.stringify output is safe here; we escape "<" so no one can close the script tag.
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, '\\u003c') }} />;
}

export const organizationLd = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'KJS India Pvt. Ltd.',
  description: 'Contract manufacturer and private-label partner for coffee, tea, health drinks and confectionery.',
  foundingDate: String(SITE.since),
  email: SITE.email,
  telephone: SITE.phone,
  address: {
    '@type': 'PostalAddress',
    streetAddress: 'Plot No. 1 & 2, Phase-III, IDA Pashamylaram, Patancheru',
    addressLocality: 'Hyderabad',
    addressRegion: 'Telangana',
    postalCode: '502307',
    addressCountry: 'IN',
  },
};
