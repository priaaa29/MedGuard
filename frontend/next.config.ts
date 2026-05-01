import type { NextConfig } from "next";

// The browser only ever talks to this app's origin; /api/* is forwarded to FastAPI.
// Same-origin means the session cookie can stay SameSite=Lax and no CORS is needed.
const BACKEND_URL = process.env.MEDGUARD_API_URL ?? "http://127.0.0.1:8000";
const IS_PRODUCTION = process.env.NODE_ENV === "production";

// 'unsafe-inline' for scripts: Next and next-themes inject small inline scripts, and a
// nonce-based policy would make every page dynamic (no static shells). Everything is
// still restricted to this origin; no third-party scripts, frames or connections.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");

const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Frame-Options", value: "DENY" },
  // Uploads use the file picker, which needs no camera permission.
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), interest-cohort=()" },
  // Dev server needs eval for fast refresh, so the CSP only applies to production builds.
  ...(IS_PRODUCTION ? [{ key: "Content-Security-Policy", value: CSP }] : []),
];

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
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
  experimental: {
    // Local `next start`/`next dev` proxy: reading a prescription is one Claude call
    // (10–30 s), close to the 30 s default. Routines are built in the background, so
    // no request waits on them. (On Vercel the CDN's own 120 s limit applies instead.)
    proxyTimeout: 120_000,
    // Prescription uploads are up to 10 MB plus multipart overhead.
    proxyClientMaxBodySize: "11mb",
  },
};

export default nextConfig;
