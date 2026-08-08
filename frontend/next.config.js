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
    const backendUrl =
      process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    return [
      // ── Specific backend auth routes (profile, logout, me, google) ──────
      // NOTE: /api/auth/session, /api/auth/providers, /api/auth/signin,
      //       /api/auth/signout, /api/auth/callback, /api/auth/error,
      //       /api/auth/_log — these are ALL handled by Next.js [...nextauth]
      //       and must NOT be proxied to FastAPI.
      {
        source: "/api/auth/profile/:path*",
        destination: `${backendUrl}/api/auth/profile/:path*`,
      },
      {
        source: "/api/auth/profile",
        destination: `${backendUrl}/api/auth/profile`,
      },
      {
        source: "/api/auth/logout",
        destination: `${backendUrl}/api/auth/logout`,
      },
      {
        source: "/api/auth/me",
        destination: `${backendUrl}/api/auth/me`,
      },
      // ── All other /api/* routes → FastAPI backend ────────────────────────
      // Explicitly excludes /api/auth/* so NextAuth keeps control
      {
        source: "/api/data/:path*",
        destination: `${backendUrl}/api/data/:path*`,
      },
      {
        source: "/api/predict/:path*",
        destination: `${backendUrl}/api/predict/:path*`,
      },
      {
        source: "/api/reports/:path*",
        destination: `${backendUrl}/api/reports/:path*`,
      },
      {
        source: "/api/chat/:path*",
        destination: `${backendUrl}/api/chat/:path*`,
      },
      {
        source: "/api/llm/:path*",
        destination: `${backendUrl}/api/llm/:path*`,
      },
      {
        source: "/api/conversation/:path*",
        destination: `${backendUrl}/api/conversation/:path*`,
      },
      {
        source: "/api/admin/:path*",
        destination: `${backendUrl}/api/admin/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

module.exports = nextConfig;
