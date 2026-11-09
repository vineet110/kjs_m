// Our 404 page, inside the header and footer (CR4). Shown when a public page calls notFound() (e.g. a product
// that doesn't exist), and for any unknown URL through [...rest]/page.tsx.
import type { Metadata } from 'next';
import ErrorPanel from '@/components/public/ErrorPanel';

export const metadata: Metadata = { title: 'Page not found' };

export default function NotFound() {
  return (
    <ErrorPanel
      title="We couldn't find that page"
      text="The link may be old, or the product may have moved. Try our products page or the home page."
    />
  );
}
