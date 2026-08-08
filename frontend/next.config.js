/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  devIndicators: false,
  async redirects() {
    return [
      {
        source: "/",
        destination: "/dashboard",
        permanent: true,
      },
    ];
  },
  async rewrites() {
    // If USE_EXTERNAL_BACKEND is set to "true", proxy to backendUrl; otherwise use Next.js App Router mock handlers
    if (process.env.USE_EXTERNAL_BACKEND === "true") {
      const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
      return [
        { source: "/api/data/:path*", destination: `${backendUrl}/api/data/:path*` },
        { source: "/api/predict/:path*", destination: `${backendUrl}/api/predict/:path*` },
        { source: "/api/reports/:path*", destination: `${backendUrl}/api/reports/:path*` },
        { source: "/api/llm/:path*", destination: `${backendUrl}/api/llm/:path*` },
        { source: "/api/conversation/:path*", destination: `${backendUrl}/api/conversation/:path*` },
        { source: "/api/admin/:path*", destination: `${backendUrl}/api/admin/:path*` },
      ];
    }
    return [];
  },
};

module.exports = nextConfig;
