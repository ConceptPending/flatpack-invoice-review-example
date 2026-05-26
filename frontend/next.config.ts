import type { NextConfig } from "next";

// The /api/* proxy is implemented as a Route Handler at
// src/app/api/[...path]/route.ts so the API_URL env var is read at runtime
// (not baked into the build). One Docker image works across environments.

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
