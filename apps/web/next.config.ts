import type { NextConfig } from "next";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://api:8000";

const nextConfig: NextConfig = {
  // Emits a self-contained server bundle so the runtime image can skip
  // node_modules entirely.
  output: "standalone",
  reactStrictMode: true,

  async rewrites() {
    return [
      {
        // The browser only ever talks to localhost:3000. This proxy is why the
        // API's httpOnly cookies are first-party — which in turn is why there is
        // no CORS configuration and no token in localStorage anywhere.
        source: "/api/v1/:path*",
        destination: `${API_INTERNAL_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
