// The gold "page is loading" bar. Drawn on the bottom edge of its nearest positioned parent: the site
// header (SiteHeader), so it is always in the right place, with or without the offers ticker above.
// SiteHeader renders it once, hidden; CSS shows it (globals.css, .page-progress).
export default function ProgressBar({ className = '' }: { className?: string }) {
  return (
    <div className={`pointer-events-none absolute inset-x-0 bottom-0 h-[3px] overflow-hidden bg-gold/15 ${className}`} role="progressbar" aria-label="Loading page">
      <div className="h-full w-1/4 animate-progress rounded-full bg-gradient-to-r from-gold-light via-gold to-gold-dark motion-reduce:w-full motion-reduce:animate-none" />
    </div>
  );
}
