import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Without this, Next.js 16 blocks dev-only resources (including client-bundle hydration
   * chunks, not just HMR) when loaded via 127.0.0.1 instead of localhost - see DECISIONS.md. */
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
