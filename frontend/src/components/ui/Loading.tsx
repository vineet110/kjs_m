// What a staff page shows while its data loads: a small spinner and "Loading…", the same everywhere.
import Spinner from './Spinner';

export default function Loading({ className = '' }: { className?: string }) {
  return (
    <p role="status" className={`flex items-center gap-2 text-sm text-slate-500 ${className}`}>
      <Spinner />
      Loading…
    </p>
  );
}
