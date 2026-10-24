import type { Metadata } from 'next';
import EnquiryForm from '@/components/public/EnquiryForm';
import { texts } from '@/lib/api';
import { SITE } from '@/lib/site';

export const metadata: Metadata = { title: 'Contact', description: 'Send KJS India an enquiry for contract manufacturing or private label.' };

export default async function ContactPage() {
  const t = await texts();
  return (
    <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 md:grid-cols-5">
      <div className="space-y-4 md:col-span-2">
        <p className="eyebrow">Contact</p>
        <h1 className="text-3xl font-bold">Talk to our sales team</h1>
        <p className="text-slate-600">{t['contact.intro'] ?? 'For brands, distributors, retailers and importers. Bulk and export orders.'}</p>
        <div className="card space-y-2 p-5 text-sm">
          <p><span className="font-semibold">Phone / WhatsApp:</span> {SITE.phone}</p>
          <p><span className="font-semibold">Email:</span> <a className="underline" href={`mailto:${SITE.email}`}>{SITE.email}</a></p>
          <p><span className="font-semibold">Factory:</span> {SITE.address}</p>
          <p className="text-slate-500">Working days: Monday to Saturday.</p>
        </div>
      </div>
      <div className="card p-6 md:col-span-3">
        <EnquiryForm title="Send an enquiry" />
      </div>
    </div>
  );
}
