import type { NextConfig } from "next";

// /api/* is served by the Python API (api/index.py).
// - Local dev: `npm run api` starts it on :8000 and this rewrite proxies to it.
// - Vercel: api/index.py deploys as a Python function; requests go to /api/.
// - Hosting the API elsewhere: set API_URL (e.g. https://my-api.onrender.com).
const apiUrl =
  process.env.API_URL ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: apiUrl ? `${apiUrl}/api/:path*` : "/api/",
      },
    ];
  },
};

export default nextConfig;
