// What a buyer sees when a public page can't be shown (CR4): a short message, "Try again" (when it may help)
// and our phone, WhatsApp and email, so a buyer who hits an error can still reach sales.
// Used by error.tsx, global-error.tsx and not-found.tsx. Plain links (<a>), not next/link: after a crash
// a full page load is the safest way back.
import { SITE } from '@/lib/site';

export default function ErrorPanel({ title, text, onRetry }: { title: string; text: string; onRetry?: () => void }) {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="mt-3 text-slate-600">{text}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {onRetry && <button onClick={onRetry} className="btn-dark">Try again</button>}
        <a href="/" className="btn-ghost">Go to the home page</a>
      </div>
      <p className="mt-8 text-sm text-slate-600">
        Need help now? Call{' '}
        <a href={`tel:${SITE.phone.replace(/\s/g, '')}`} className="font-semibold underline">{SITE.phone}</a>
        , <a href={SITE.whatsapp} target="_blank" rel="noopener" className="font-semibold underline">WhatsApp us</a>
        {' '}or email <a href={`mailto:${SITE.email}`} className="font-semibold underline">{SITE.email}</a>.
      </p>
    </div>
  );
}
