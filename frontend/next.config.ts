import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8100";

const nextConfig: NextConfig = {
  output: "standalone",
  // Django's APPEND_SLASH owns API path normalization. Without this, Next
  // removes the slash and Django adds it back, producing a redirect loop.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*/`,
      },
    ];
  },
};

export default nextConfig;
