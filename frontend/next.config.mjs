/** @type {import('next').NextConfig} */
// Separate output folders: dev (.next), production (.next-prod), so a production build never fights a dev server.
// NEXT_DIST_DIR overrides both.
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || (process.env.NODE_ENV === 'production' ? '.next-prod' : '.next'),
  // Docker builds set NEXT_OUTPUT=standalone: a self-contained server.js with only the modules it needs
  ...(process.env.NEXT_OUTPUT === 'standalone' ? { output: 'standalone' } : {}),
};
export default nextConfig;
