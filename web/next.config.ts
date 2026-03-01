import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Suppress punycode deprecation warning from date-fns
  serverExternalPackages: [],
};

export default nextConfig;
