import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    // sentinel-api lives on 'intranet' only — never on 'internet'.
    // All /api/* traffic from the browser arrives at sentinel-ui via Traefik,
    // and the Next.js server forwards it to sentinel-api over the intranet.
    // INTERNAL_API_URL is set in docker-compose; falls back to the container
    // name for local dev (when running with docker compose directly).
    const apiBase = process.env.INTERNAL_API_URL ?? "http://sentinel-api:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
