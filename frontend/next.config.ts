import type { NextConfig } from "next";

const apiDestination =
  process.env.INTERNAL_API_URL
    ? `${process.env.INTERNAL_API_URL}/:path*`
    : "http://127.0.0.1:8000/api/v1/:path*";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: apiDestination,
      },
    ];
  },
};

export default nextConfig;
