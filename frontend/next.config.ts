import type { NextConfig } from "next";

// The browser only ever talks to this app's origin; /api/* is forwarded to FastAPI.
// Same-origin means the session cookie can stay SameSite=Lax and no CORS is needed.
const BACKEND_URL = process.env.MEDGUARD_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    // Pin the root: a stray lockfile higher up the filesystem otherwise confuses root detection.
    root: import.meta.dirname,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
  experimental: {
    // Building a routine makes up to three Claude calls; the default 30 s rewrite
    // timeout would cut it off.
    proxyTimeout: 240_000,
    // Prescription uploads are up to 10 MB plus multipart overhead.
    proxyClientMaxBodySize: "11mb",
  },
};

export default nextConfig;
