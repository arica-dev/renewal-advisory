import type { NextConfig } from "next";

// /api/* is served by the Python API (api/index.py).
// - Local dev: `npm run api` starts it on :8000 and this rewrite proxies to it.
// - Production: set API_URL to the deployed API (a separate Vercel project
//   using the FastAPI preset, e.g. https://renewal-advisory-api.vercel.app).
const apiUrl =
  process.env.API_URL ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);

const nextConfig: NextConfig = {
  async rewrites() {
    return apiUrl ? [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }] : [];
  },
};

export default nextConfig;
