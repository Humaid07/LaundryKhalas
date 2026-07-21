/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Defaults to ".next"; overridable so an isolated build/verify never collides
  // with a running `next dev` server that owns the shared ".next" directory.
  distDir: process.env.LK_DIST_DIR || ".next",
  async redirects() {
    return [
      // Finance was renamed to "Finance & Compliance" and moved.
      { source: "/finance", destination: "/finance-compliance", permanent: false },
    ];
  },
};

module.exports = nextConfig;
