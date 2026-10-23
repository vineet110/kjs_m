import type { MetadataRoute } from 'next';

const BASE = process.env.SITE_URL || 'http://localhost:3000';

export default function robots(): MetadataRoute.Robots {
  return {
    // Public pages are for Google; the staff portal and API are not.
    rules: [{ userAgent: '*', allow: '/', disallow: ['/admin', '/employee', '/api'] }],
    sitemap: `${BASE}/sitemap.xml`,
  };
}
