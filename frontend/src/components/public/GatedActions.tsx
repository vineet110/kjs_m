// The four gated buttons on a product page (D3: browsing is free, these ask for details once).
import EnquiryButton from './EnquiryButton';

export default function GatedActions({ productSlug, productName }: { productSlug: string; productName: string }) {
  const actions = [
    { source: 'price_sheet', label: 'Request price sheet', primary: true },
    { source: 'spec_pdf', label: 'Get spec sheet' },
    { source: 'sample', label: 'Request a sample' },
    { source: 'quote', label: 'Get a quote' },
  ] as const;
  return (
    <div className="flex flex-wrap gap-2">
      {actions.map((a) => (
        <EnquiryButton
          key={a.source}
          label={a.label}
          source={a.source}
          productSlug={productSlug}
          title={`${productName}: ${a.label.toLowerCase()}`}
          className={'primary' in a ? 'btn-gold' : 'btn-ghost'}
        />
      ))}
    </div>
  );
}
