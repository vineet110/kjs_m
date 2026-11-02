// A small spinning ring (takes the text colour). Decorative: the text next to it says what is happening.
// Used on public and staff pages, so it lives outside portal/. Still for visitors who ask for reduced motion.
export default function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return <span aria-hidden className={`inline-block shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none ${className}`} />;
}
