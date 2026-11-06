import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin();

// Where Next.js reaches FastAPI. Browser calls go to /api/* on our own domain and are
// proxied here, so the session cookie stays first-party (simpler and safer than CORS).
const API = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';

// Site pictures on Cloudflare R2 (see src/lib/assets.ts). next/image only loads outside pictures from
// addresses listed here, so the bucket's address is allowed, and nothing else.
const ASSET_BASE = (process.env.NEXT_PUBLIC_ASSET_BASE || '').replace(/\/+$/, '');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false, // don't advertise the framework in every response
  devIndicators: false, // no Next.js "N" badge in the corner during `npm run dev` (demos, screenshots)
  // A separate build folder (e.g. NEXT_DIST_DIR=.next-e2e) lets a test build run without
  // touching the .next folder that `npm run dev` is using.
  distDir: process.env.NEXT_DIST_DIR || '.next',
  // The Docker image sets NEXT_STANDALONE=1: the build then contains its own small server
  // (server.js + only the packages it needs), so the image doesn't carry all of node_modules.
  output: process.env.NEXT_STANDALONE === '1' ? 'standalone' : undefined,
  images: ASSET_BASE ? { remotePatterns: [new URL(`${ASSET_BASE}/**`)] } : undefined,
  // The Capabilities pages were removed (Nov 2026). They were in the sitemap, so Google and old
  // bookmarks still have them: send those visitors to Private label instead of a 404.
  async redirects() {
    return [{ source: '/capabilities/:path*', destination: '/private-label', permanent: true }];
  },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${API}/api/:path*` }];
  },
};

export default withNextIntl(nextConfig);
