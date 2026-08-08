"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

const NAV = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "EOI Analysis", href: "/dashboard/eoi-analysis" },
  { label: "Shortage", href: "/dashboard/shortage" },
  { label: "Predictors", href: "/dashboard/predictors" },
  { label: "Pathway", href: "/dashboard/pathway" },
  { label: "Approval", href: "/dashboard/approval" },
  { label: "Chat", href: "/dashboard/chat" },
  { label: "Reports", href: "/dashboard/reports" },
  { label: "Admin", href: "/dashboard/admin", adminOnly: true },
];

export default function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  const role = (session?.user as any)?.role;
  const isAdmin = role === "admin" || role === "superadmin";

  const [rowCount, setRowCount] = useState<string>("Loading...");
  const [profilePic, setProfilePic] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    const fetchRowCount = async () => {
      try {
        const res = await fetch("/api/data/row-count");
        const data = await res.json();
        setRowCount(
          `${data.formatted} rows · ${data.database === "migration_db (MySQL)" ? "migration_db (MySQL)" : data.database}`,
        );
      } catch (error) {
        console.error("Failed to fetch row count:", error);
        setRowCount("N/A · migration_db (MySQL)");
      }
    };
    fetchRowCount();
  }, []);

  useEffect(() => {
    const fetchProfilePic = async () => {
      const token = (session?.user as any)?.accessToken;
      if (!token) return;
      try {
        const res = await fetch(`/api/auth/profile`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setProfilePic(data.profile_picture);
        }
      } catch (error) {
        console.error("Failed to fetch profile pic:", error);
      }
    };

    fetchProfilePic();

    window.addEventListener("profileUpdate", fetchProfilePic);
    return () => window.removeEventListener("profileUpdate", fetchProfilePic);
  }, [session]);

  const activeSection =
    pathname === "/dashboard"
      ? "Dashboard"
      : pathname.startsWith("/dashboard/eoi-analysis")
        ? "EOI Analysis"
        : pathname.startsWith("/dashboard/shortage")
          ? "Shortage"
          : pathname.startsWith("/dashboard/predictors")
            ? "Predictors"
            : pathname.startsWith("/dashboard/pathway")
              ? "Pathway"
              : pathname.startsWith("/dashboard/approval")
                ? "Approval"
                : pathname.startsWith("/dashboard/chat")
                  ? "Chat"
                  : pathname.startsWith("/dashboard/reports")
                    ? "Reports"
                    : pathname.startsWith("/dashboard/admin")
                      ? "Admin"
                      : "Dashboard";

  const handleLogout = async () => {
    try {
      const token = (session?.user as any)?.accessToken;
      if (token) {
        await fetch(`/api/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
      }
    } catch (error) {
      console.error("Logout API error:", error);
    }
    await signOut({ redirect: false });
    router.push("/login");
  };

  const visibleNav = NAV.filter((item) => {
    if ((item as any).adminOnly && !isAdmin) return false;
    return true;
  });

  useEffect(() => {
    setMobileMenuOpen(false);
    setUserMenuOpen(false);
  }, [pathname]);

  return (
    <nav
      style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        padding: "0 28px",
        display: "flex",
        alignItems: "center",
        height: "54px",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}
    >
      {/* Hamburger Menu Toggle (Mobile - Left) */}
      <button
        className="nav-mobile-toggle"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        style={{
          background: "transparent",
          border: "none",
          color: "var(--muted)",
          cursor: "pointer",
          padding: "4px 12px 4px 0",
          display: "none",
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {mobileMenuOpen ? (
            <path d="M18 6L6 18M6 6l12 12" />
          ) : (
            <path d="M3 12h18M3 6h18M3 18h18" />
          )}
        </svg>
      </button>

      {/* Logo */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginRight: "20px",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            background: "linear-gradient(135deg, #2a8bff, #1d4ed8)",
            borderRadius: 7,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 12,
            fontWeight: 800,
            color: "#fff",
          }}
        >
          I
        </div>
        <span
          className="nav-logo-text"
          style={{
            fontSize: "14px",
            fontWeight: 700,
            color: "var(--text)",
            letterSpacing: "-0.3px",
          }}
        >
          Inter
        </span>
        <span className="nav-logo-sub" style={{ fontSize: "14px", color: "var(--muted)" }}>
          Intelligence
        </span>
      </div>

      {/* Nav links (Desktop) */}
      <div className="nav-links-desktop" style={{ display: "flex", height: "100%", alignItems: "stretch" }}>
        {visibleNav.map(({ label, href }) => {
          const active = activeSection === label;
          return (
            <Link
              key={label}
              href={href}
              style={{
                display: "flex",
                alignItems: "center",
                padding: "0 14px",
                fontSize: "13px",
                fontWeight: active ? 600 : 400,
                color: active ? "#2a8bff" : "var(--muted)",
                textDecoration: "none",
                borderBottom: active
                  ? "2px solid #2a8bff"
                  : "2px solid transparent",
                borderTop: "2px solid transparent",
                transition: "color 0.15s",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.color = "var(--text)";
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.color = "var(--muted)";
                }
              }}
            >
              {label}
            </Link>
          );
        })}
      </div>

      {/* Right side */}
      <div
        style={{
          marginLeft: "auto",
          display: "flex",
          alignItems: "center",
          gap: "12px",
        }}
      >
        <ThemeToggle />

        <span
          className="nav-live-badge"
          style={{
            background: "#10b98120",
            color: "#10b981",
            fontSize: "10px",
            fontWeight: 700,
            padding: "2px 8px",
            borderRadius: "4px",
            border: "1px solid #10b98140",
            marginLeft: "8px",
          }}
        >
          ● LIVE
        </span>
        <span className="nav-row-count" style={{ fontSize: "11px", color: "var(--muted)" }}>
          {rowCount}
        </span>

        {/* User info dropdown */}
        {session?.user ? (
          <div style={{ position: "relative" }}>
            <div
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                cursor: "pointer",
                padding: "4px 8px",
                borderRadius: "8px",
                background: userMenuOpen ? "var(--border)30" : "transparent",
                transition: "background 0.2s",
              }}
            >
              <div
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: "50%",
                  background: isAdmin
                    ? "linear-gradient(135deg, #ef4444, #dc2626)"
                    : "linear-gradient(135deg, #2a8bff, #8b5cf6)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  fontWeight: 800,
                  color: "white",
                  flexShrink: 0,
                  overflow: "hidden",
                }}
              >
                {profilePic ? (
                  <img
                    src={profilePic}
                    alt="Profile"
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                    }}
                  />
                ) : (
                  session.user.name?.[0]?.toUpperCase() || "U"
                )}
              </div>
              <div className="nav-user-text">
                <p
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text)",
                    lineHeight: 1,
                  }}
                >
                  {session.user.name}
                </p>
                <p
                  style={{
                    fontSize: 9,
                    color: isAdmin
                      ? role === "superadmin"
                        ? "#8b5cf6"
                        : "#ef4444"
                      : "var(--muted)",
                    marginTop: 2,
                    lineHeight: 1,
                    fontWeight: role === "superadmin" ? 800 : 400,
                  }}
                >
                  {role || "user"}
                </p>
              </div>
            </div>

            {userMenuOpen && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  right: 0,
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "10px",
                  boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
                  padding: "6px",
                  width: "160px",
                  zIndex: 110,
                }}
              >
                <Link
                  href="/dashboard/profile"
                  style={{
                    display: "block",
                    padding: "8px 12px",
                    fontSize: "13px",
                    color: "var(--text)",
                    textDecoration: "none",
                    borderRadius: "6px",
                    transition: "background 0.2s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--border)20")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  Profile Details
                </Link>
                <div style={{ height: "1px", background: "var(--border)", margin: "4px 0" }} />
                <button
                  onClick={handleLogout}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    padding: "8px 12px",
                    fontSize: "13px",
                    color: "#ef4444",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    borderRadius: "6px",
                    transition: "background 0.2s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#ef444410")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link
            href="/login"
            style={{
              fontSize: "12px",
              fontWeight: 700,
              color: "#fff",
              background: "#2a8bff",
              padding: "6px 16px",
              borderRadius: "6px",
              textDecoration: "none",
              transition: "opacity 0.2s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.9")}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
          >
            LOGIN
          </Link>
        )}
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div
          className="nav-mobile-dropdown"
          style={{
            position: "absolute",
            top: "54px",
            left: 0,
            right: 0,
            background: "var(--surface)",
            borderBottom: "1px solid var(--border)",
            padding: "8px 0",
            display: "flex",
            flexDirection: "column",
            zIndex: 99,
          }}
        >
          {visibleNav.map(({ label, href }) => (
            <Link
              key={label}
              href={href}
              style={{
                padding: "12px 28px",
                fontSize: "14px",
                color: activeSection === label ? "#2a8bff" : "var(--muted)",
                textDecoration: "none",
                fontWeight: activeSection === label ? 600 : 400,
                background: activeSection === label ? "var(--border)20" : "transparent",
              }}
            >
              {label}
            </Link>
          ))}
          {!session?.user && (
            <Link
              href="/login"
              style={{
                padding: "12px 28px",
                fontSize: "14px",
                color: "#2a8bff",
                textDecoration: "none",
                fontWeight: 600,
                borderTop: "1px solid var(--border)",
                marginTop: "4px",
              }}
            >
              Login / Sign In
            </Link>
          )}
        </div>
      )}
    </nav>
  );
}
