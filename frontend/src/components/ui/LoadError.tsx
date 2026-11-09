// What a staff page shows when its data could not be loaded (R40), instead of "Loading…" forever or an
// empty list that looks like "nothing here": the reason, the error code for support, and "Try again".
import { ApiFailure } from '@/lib/api';

/** The text to show for a failed request: the server's message, a message the page already wrote (a
 *  string), or a plain one for a network error. */
export function errorText(e: unknown, fallback = 'Could not load.'): string {
  if (typeof e === 'string' && e) return e;
  return e instanceof ApiFailure ? e.message : fallback;
}

export default function LoadError({ error, onRetry, className = '' }: { error: unknown; onRetry: () => void; className?: string }) {
  const code = error instanceof ApiFailure ? error.body.request_id : null;
  return (
    <div role="alert" className={`flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 ${className}`}>
      <span>
        Could not load. {errorText(error, 'The server did not answer.')}
        {code && <span className="ml-1 text-xs text-red-700/80">(code {code})</span>}
      </span>
      <button onClick={onRetry} className="btn-ghost py-1">Try again</button>
    </div>
  );
}
