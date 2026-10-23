import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin();

// Where Next.js reaches FastAPI. Browser calls go to /api/* on our own domain and are
// proxied here, so the session cookie stays first-party (simpler and safer than CORS).
const API = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${API}/api/:path*` }];
  },
};

export default withNextIntl(nextConfig);
