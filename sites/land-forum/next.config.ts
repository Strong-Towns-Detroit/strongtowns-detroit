import type { NextConfig } from "next";
import { resolve } from "node:path";

const nextConfig: NextConfig = {
  output: "export",
  turbopack: { root: resolve(process.cwd(), "../..") },
  trailingSlash: true,
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
