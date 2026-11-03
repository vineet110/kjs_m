// "Up to X% OFF" (UI step 6): shown only when staff set an offer on the product in Admin > Products.
import { offerLabel } from '@/lib/catalogue';

export default function OfferBadge({ percent, className = '' }: { percent: number | null | undefined; className?: string }) {
  const label = offerLabel(percent);
  if (!label) return null;
  return <span className={`rounded-full bg-red-600 px-2 py-0.5 text-[11px] font-bold text-white shadow-sm ${className}`}>{label}</span>;
}
