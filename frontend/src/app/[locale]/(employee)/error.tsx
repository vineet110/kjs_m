'use client'; // error pages must run in the browser (React error boundary)
// An employee page crashed: show the error inside the portal (the sidebar stays), with "Try again".
import { useEffect } from 'react';
import LoadError from '@/components/ui/LoadError';

export default function EmployeeError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => console.error(error), [error]);
  return <LoadError error={error} onRetry={retry} />;
}
