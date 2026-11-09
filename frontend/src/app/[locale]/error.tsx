'use client'; // error pages must run in the browser (React error boundary)
// Catches a crash in a layout one level down (e.g. the public site's layout), which that folder's own
// error.tsx can't catch. Our header and footer are part of what failed, so this page shows without them.
// A crash in the root layout ([locale]/layout.tsx) goes to app/global-error.tsx.
import { useEffect } from 'react';
import ErrorPanel from '@/components/public/ErrorPanel';

export default function LocaleError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => console.error(error), [error]);
  return (
    <ErrorPanel
      title="Something went wrong"
      text="This page could not be loaded. Please try again in a minute."
      onRetry={retry}
    />
  );
}
