'use client'; // error pages must run in the browser (React error boundary)
// Last line of defence: the root layout ([locale]/layout.tsx) itself crashed. This page replaces it, so it
// needs its own <html> and <body> and imports the styles itself.
import '@/app/globals.css';
import { useEffect } from 'react';
import ErrorPanel from '@/components/public/ErrorPanel';

export default function GlobalError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => console.error(error), [error]);
  return (
    <html lang="en">
      <body className="bg-paper text-slate-900 antialiased">
        <title>Something went wrong | KJS India</title>
        <ErrorPanel
          title="Something went wrong"
          text="Our website could not be loaded. Please try again in a minute."
          onRetry={retry}
        />
      </body>
    </html>
  );
}
