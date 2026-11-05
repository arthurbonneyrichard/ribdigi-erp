function apiProxyTarget() {
  const raw =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8000/api/v1';
  return raw.replace(/\/$/, '');
}

// The analytics host follows NEXT_PUBLIC_UMAMI_SRC. blob: frames and media show attachment previews.
const ANALYTICS_ORIGIN = new URL(process.env.NEXT_PUBLIC_UMAMI_SRC || 'https://analytics.ribdigihouse.com/script.js').origin;
const CSP =
  `default-src 'self'; script-src 'self' 'unsafe-inline' ${ANALYTICS_ORIGIN}; ` +
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; " +
  "img-src 'self' data: blob: https:; media-src 'self' blob:; connect-src 'self' https: wss:; frame-src 'self' https: blob:; " +
  "worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self' https:";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // The app never uses next/image. Keep the image optimizer off: its endpoint carries
  // unauthenticated RCE/DoS advisories on Next 14 (blocked again in proxy.ts).
  images: { unoptimized: true },
  // Cloud/remote VMs often miss native FS events; poll so Fast Refresh sees edits.
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        ...(config.watchOptions || {}),
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
  // Same baseline as the API. Public booking/ordering/shop pages stay embeddable on a shop's own website.
  async headers() {
    const base = [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
      { key: 'Permissions-Policy', value: 'camera=(self), microphone=(), geolocation=()' },
      // Dev needs eval for hot reload, so the full policy is only enforced on production builds.
      process.env.NODE_ENV === 'production'
        ? { key: 'Content-Security-Policy', value: CSP }
        : { key: 'Content-Security-Policy-Report-Only', value: CSP },
    ];
    return [
      { source: '/:path*', headers: base },
      { source: '/((?!book|order|stay|storefront|shop).*)', headers: [{ key: 'X-Frame-Options', value: 'DENY' }] },
    ];
  },
  async redirects() {
    return [{ source: '/login', destination: '/', permanent: false }];
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiProxyTarget()}/:path*`,
      },
    ];
  },
};

export default nextConfig;
