/** @type {import('next').NextConfig} */
// Separate output folders: dev (.next), production (.next-prod), so a production build never fights a dev server.
// NEXT_DIST_DIR overrides both.
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || (process.env.NODE_ENV === 'production' ? '.next-prod' : '.next'),
};
export default nextConfig;
