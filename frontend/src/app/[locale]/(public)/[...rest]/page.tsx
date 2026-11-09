// Any URL that matches no page lands here and shows our not-found.tsx (with header and footer), not Next's
// bare default 404. Real pages always win over this catch-all, so it only ever gets unknown URLs.
import { notFound } from 'next/navigation';

export default function UnknownPage() {
  notFound();
}
