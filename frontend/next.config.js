/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  // Enable standalone output for Docker production builds
  // This creates a minimal server.js with only necessary dependencies
  output: 'standalone',
}

module.exports = nextConfig