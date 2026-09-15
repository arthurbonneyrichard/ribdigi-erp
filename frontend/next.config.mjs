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
};

export default nextConfig;
