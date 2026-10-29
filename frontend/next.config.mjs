function apiProxyTarget() {
  const raw =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8000/api/v1';
  return raw.replace(/\/$/, '');
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
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
