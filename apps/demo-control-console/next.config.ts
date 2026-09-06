import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Without this, Next.js 16 blocks dev-only resources (including the client bundle chunks
   * needed for hydration, not just HMR) when the page is loaded via 127.0.0.1 instead of
   * localhost - silently leaving every "use client" component (buttons, live polling) inert. */
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
