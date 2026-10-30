'use client';
// Put on a product page: remembers in this browser that the visitor opened it (lib/history.ts),
// so the home page can recommend similar products. Renders nothing.
import { useEffect } from 'react';
import { rememberViewed } from '@/lib/history';

export default function TrackView({ slug }: { slug: string }) {
  useEffect(() => rememberViewed(slug), [slug]);
  return null;
}
