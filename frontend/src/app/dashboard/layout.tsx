"use client";
import { useEffect, useState } from "react";
import Swal from "sweetalert2";
import { SessionProvider, useSession } from "next-auth/react";
import dynamic from 'next/dynamic';
const TopNav = dynamic(() => import('@/components/layout/TopNav'), { ssr: false });
import { DataCacheProvider, useDataCache } from "@/lib/DataCacheContext";
import { usePathname, useRouter } from "next/navigation";
import { waitForBackend } from "@/lib/fetchWithRetry";

const PREFETCH_URLS = [
  "/api/data/summary",
  "/api/data/eoi/monthly",
  "/api/data/quota",
  "/api/data/osl-trend",
  "/api/data/eoi/occupations",
  "/api/data/shortage-heatmap?year=2025",
];

/**
 * PrefetchOnMount — waits until the backend /health endpoint responds
 * before firing prefetch requests. This prevents ECONNREFUSED / socket-hang-up
 * errors during the backend's 30s–3min startup window (model loading + Chroma).
 */
function PrefetchOnMount() {
  const { prefetch } = useDataCache();
  const [backendReady, setBackendReady] = useState<boolean | null>(true);

  useEffect(() => {
    let cancelled = false;
    waitForBackend(10_000, 1_000).then((ready) => {
      if (cancelled) return;
      setBackendReady(ready);
      PREFETCH_URLS.forEach((url) => prefetch(url));
    });
    return () => { cancelled = true; };
  }, []);

  // Show a subtle banner while the backend is still starting up
  if (backendReady === null) {
    return (
      <div
        style={{
          position: "fixed",
          bottom: 16,
          right: 16,
          zIndex: 9999,
          background: "rgba(30,39,97,0.92)",
          color: "#CADCFC",
          padding: "8px 16px",
          borderRadius: 8,
          fontSize: 13,
          display: "flex",
          alignItems: "center",
          gap: 8,
          boxShadow: "0 2px 12px rgba(0,0,0,0.4)",
          backdropFilter: "blur(6px)",
        }}
      >
        <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>⏳</span>
        Backend starting…
        <style>{`@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }`}</style>
      </div>
    );
  }

  return null;
}


function AuthGuard({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Only protect sub-routes of /dashboard, allow /dashboard itself to be public
    const isMainDashboard = pathname === "/dashboard";
    const isSubRoute = pathname.startsWith("/dashboard/") && pathname !== "/dashboard";

    if (status === "unauthenticated" && isSubRoute) {
      // Immediately redirect back to the public dashboard so they don't see the protected page
      router.replace("/dashboard");
      
      // Then show the alert
      Swal.fire({
        icon: 'warning',
        title: 'Access Denied',
        text: 'You have to login first to access this page.'
      }).then(() => {
        router.push("/login");
      });
      return;
    }

    // Role-based access control for admin pages
    if (status === "authenticated" && pathname.startsWith("/dashboard/admin")) {
      const userRole = (session?.user as any)?.role;
      if (userRole !== "superadmin" && userRole !== "admin") {
        // Redirect unauthorized users back to dashboard
        router.replace("/dashboard");
      }
    }
  }, [status, pathname, router, session]);

  // Prevent flashing of protected content while redirecting
  const isSubRoute = pathname.startsWith("/dashboard/") && pathname !== "/dashboard";
  const isUnauthorized = status === "unauthenticated" && isSubRoute;
  
  const isAdminRoute = pathname.startsWith("/dashboard/admin");
  const isAuthorizedAdmin = status === "authenticated" && ((session?.user as any)?.role === "superadmin" || (session?.user as any)?.role === "admin");
  
  // If they are unauthorized, we return null so the protected page components 
  // don't even mount or fetch data in the background.
  if (isUnauthorized || (isAdminRoute && !isAuthorizedAdmin)) {
    return null; 
  }

  return <>{children}</>;
}

import { ClientOnly } from "@/components/shared";
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SessionProvider>
      <AuthGuard>
        <DataCacheProvider>
          <PrefetchOnMount />
          <div className="min-h-screen" style={{ backgroundColor: "var(--bg)" }} suppressHydrationWarning>
            <TopNav />
            <ClientOnly>
              <main>{children}</main>
            </ClientOnly>
          </div>
        </DataCacheProvider>
      </AuthGuard>
    </SessionProvider>
  );
}
