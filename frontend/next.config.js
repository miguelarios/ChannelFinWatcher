/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  // Note: Not using 'standalone' output mode
  // Using standard Next.js production build with 'npm start'
}

module.exports = nextConfig