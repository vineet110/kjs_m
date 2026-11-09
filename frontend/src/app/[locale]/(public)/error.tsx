'use client'; // error pages must run in the browser (React error boundary)
// A public page crashed (e.g. the API is down or too slow: CR4). Shown inside our header and footer.
// A crash in the (public) layout itself is caught one level up, in [locale]/error.tsx.
import { useEffect } from 'react';
import ErrorPanel from '@/components/public/ErrorPanel';

export default function PublicError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => console.error(error), [error]);
  return (
    <ErrorPanel
      title="This page could not be loaded"
      text="Something went wrong on our side. Please try again in a minute."
      onRetry={retry}
    />
  );
}
