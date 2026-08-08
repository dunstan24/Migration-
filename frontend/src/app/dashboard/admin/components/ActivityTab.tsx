import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { C, Pagination } from "@/components/ui";

const BACKEND_URL = "";

interface Activity {
  id: number;
  user_id: number | null;
  username: string;
  role?: string;
  action: string;
  severity: string;
  timestamp: string;
  ip_address: string;
  status: string;
  details?: string;
}

interface DashboardData {
  activities: Activity[];
  statistics: {
    period_days: number;
    total_logins: number;
    failed_login_attempts: number;
    unique_active_users: number;
    critical_events: number;
  };
  heatmap: Record<string, number>;
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_next: boolean;
    page: number;
  };
}

const sev = (s: string) => {
  if (s === "critical") return { bg: `${C.red}20`, color: C.red, border: `${C.red}40` };
  if (s === "warning")  return { bg: `${C.amber}20`, color: C.amber, border: `${C.amber}40` };
  return { bg: `${C.blue}20`, color: C.blue, border: `${C.blue}40` };
};

export default function ActivityTab() {
  const { data: session, status } = useSession();
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const role = (session?.user as any)?.role;
    if (status === "authenticated" && (role === "admin" || role === "superadmin")) {
      fetchDashboardData();
    }
  }, [days, selectedAction, page, status, session]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const limit = 50;
      const offset = (page - 1) * limit;
      const queryParams = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        days: days.toString(),
        ...(selectedAction && { action: selectedAction }),
      });
      const res = await fetch(
        `${BACKEND_URL}/api/admin/dashboard/activity?${queryParams}`,
        {
          headers: {
            ...(session?.user?.accessToken && {
              Authorization: `Bearer ${session.user.accessToken}`,
            }),
          },
        }
      );
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Failed to fetch dashboard data: ${res.status} ${errText}`);
      }
      setDashboardData(await res.json());
    } catch (error) {
      console.error("Error fetching dashboard:", error);
    } finally {
      setLoading(false);
    }
  };

  if (status === "loading" || !dashboardData) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center", color: C.muted, fontSize: 13 }}>
        <div style={{ width: 24, height: 24, border: `2px solid var(--border)`, borderTopColor: C.blue, borderRadius: "50%", margin: "0 auto 12px", animation: "spin 0.8s linear infinite" }} />
        Loading dashboard...
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const stats = dashboardData.statistics;
  const hours = Object.keys(dashboardData.heatmap).sort().map((h) => ({ hour: h, count: dashboardData.heatmap[h] }));
  const maxCount = Math.max(...hours.map((h) => h.count), 1);
  const successRate = stats.total_logins > 0
    ? Math.round(((stats.total_logins - stats.failed_login_attempts) / stats.total_logins) * 100)
    : 0;

  const statCards = [
    { label: "Total Logins",     value: stats.total_logins,              color: C.blue,   sub: `${stats.period_days}d period` },
    { label: "Failed Attempts",  value: stats.failed_login_attempts,     color: C.red,    sub: "Security monitor" },
    { label: "Active Users",     value: stats.unique_active_users,       color: C.green,  sub: "Unique users" },
    { label: "Critical Events",  value: stats.critical_events,           color: C.orange, sub: "Alert level" },
    { label: "Success Rate",     value: `${successRate}%`,               color: C.purple, sub: "Login success" },
  ];

  const selectStyle: React.CSSProperties = {
    background: "var(--surface)",
    border: `1px solid var(--border)`,
    color: "var(--text)",
    borderRadius: 8,
    padding: "6px 12px",
    fontSize: 13,
    cursor: "pointer",
    outline: "none",
  };

  const btnBase: React.CSSProperties = {
    background: "var(--surface)",
    border: `1px solid var(--border)`,
    color: "var(--text)",
    borderRadius: 8,
    padding: "6px 16px",
    fontSize: 13,
    cursor: "pointer",
  };

  return (
    <div style={{ margin: "16px 0" }}>
      {/* ── Stat Cards ───────────────────────────────────────── */}
      <div style={{ 
        display: "grid", 
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", 
        gap: 14, 
        marginBottom: 24 
      }}>
        {statCards.map((card) => (
          <div key={card.label} style={{ background: "var(--surface)", border: `1px solid var(--border)`, borderRadius: 12, padding: "18px 20px" }}>
            <p style={{ fontSize: 11, color: C.muted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 8 }}>{card.label}</p>
            <p style={{ fontSize: 28, fontWeight: 800, color: card.color, lineHeight: 1, marginBottom: 4 }}>{card.value}</p>
            <p style={{ fontSize: 11, color: C.muted }}>{card.sub}</p>
          </div>
        ))}
      </div>

      {/* ── Hourly Heatmap ───────────────────────────────────── */}
      <div style={{ background: "var(--surface)", border: `1px solid var(--border)`, borderRadius: 12, padding: "20px 24px", marginBottom: 24 }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text)", marginBottom: 16 }}>Hourly Activity Heatmap</p>
        <div style={{ display: "flex", gap: 4, overflowX: "auto", paddingBottom: 8 }}>
          {hours.map(({ hour, count }) => (
            <div key={hour} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <div
                style={{
                  width: 28, height: 56, borderRadius: 6,
                  backgroundColor: `rgba(42, 139, 255, ${Math.max(0.08, count / maxCount)})`,
                  border: `1px solid rgba(42,139,255,${Math.max(0.15, count / maxCount * 0.6)})`,
                }}
                title={`${hour}: ${count} logins`}
              />
              <span style={{ fontSize: 10, color: C.muted, width: 28, textAlign: "center" }}>{hour}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Activity Log ─────────────────────────────────────── */}
      <div style={{ background: "var(--surface)", border: `1px solid var(--border)`, borderRadius: 12, overflow: "hidden" }}>
        {/* Filters */}
        <div style={{ padding: "16px 24px", borderBottom: `1px solid var(--border)`, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>Activity Log</p>
          <div style={{ display: "flex", gap: 10 }}>
            <select value={days} onChange={(e) => { setDays(parseInt(e.target.value)); setPage(1); }} style={selectStyle}>
              <option value={1}>24 Hours</option>
              <option value={7}>7 Days</option>
              <option value={30}>30 Days</option>
              <option value={90}>90 Days</option>
            </select>
            <select value={selectedAction || ""} onChange={(e) => { setSelectedAction(e.target.value || null); setPage(1); }} style={selectStyle}>
              <option value="">All Actions</option>
              <option value="login">Login</option>
              <option value="logout">Logout</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--surface-alt)", borderBottom: `1px solid var(--border)` }}>
                {["User", "Action", "Severity", "Timestamp", "IP Address", "Status"].map((h) => (
                  <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: 10, fontWeight: 700, color: C.muted, textTransform: "uppercase", letterSpacing: "0.07em" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ padding: "32px", textAlign: "center", color: C.muted, fontSize: 13 }}>Loading activities...</td></tr>
              ) : dashboardData.activities.length === 0 ? (
                <tr><td colSpan={6} style={{ padding: "32px", textAlign: "center", color: C.muted, fontSize: 13 }}>No activities found</td></tr>
              ) : (
                dashboardData.activities.map((activity, i) => {
                  const sevStyle = sev(activity.severity);
                  const okStyle = activity.status === "success"
                    ? { bg: `${C.green}20`, color: C.green, border: `${C.green}40` }
                    : { bg: `${C.red}20`,   color: C.red,   border: `${C.red}40` };
                  return (
                    <tr key={activity.id} style={{ borderBottom: `1px solid var(--border)`, background: i % 2 === 0 ? "transparent" : "var(--surface-alt)" }}>
                      <td style={{ padding: "12px 20px", fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                        {activity.username}
                        {activity.role && (
                          <div style={{ fontSize: 11, color: C.muted }}>
                            {activity.role === "superadmin" ? "👑 Super Admin" : activity.role === "admin" ? "🛡️ Administrator" : "👤 Regular User"}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "12px 20px", fontSize: 12, color: C.muted }}>{activity.action.toUpperCase()}</td>
                      <td style={{ padding: "12px 20px" }}>
                        <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, background: sevStyle.bg, color: sevStyle.color, border: `1px solid ${sevStyle.border}` }}>
                          {activity.severity}
                        </span>
                      </td>
                      <td style={{ padding: "12px 20px", fontSize: 12, color: C.muted }}>{new Date(activity.timestamp).toLocaleString()}</td>
                      <td style={{ padding: "12px 20px", fontSize: 12, fontFamily: "monospace", color: C.muted }}>{activity.ip_address || "N/A"}</td>
                      <td style={{ padding: "12px 20px" }}>
                        <span style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: 4,
                          background: okStyle.bg,
                          color: okStyle.color,
                          border: `1px solid ${okStyle.border}`
                        }}>
                          {activity.status.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div style={{ padding: "10px 20px", borderTop: `1px solid var(--border)` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <p style={{ fontSize: 12, color: C.muted }}>
              Showing{" "}
              <strong>{dashboardData.pagination.offset > 0 ? dashboardData.pagination.offset + 1 : 1}</strong>
              {" "}to{" "}
              <strong>{Math.min(dashboardData.pagination.offset + dashboardData.pagination.limit, dashboardData.pagination.total)}</strong>
              {" "}of <strong>{dashboardData.pagination.total}</strong>
            </p>
          </div>
          <Pagination 
            page={page} 
            totalPages={Math.ceil(dashboardData.pagination.total / dashboardData.pagination.limit)} 
            setPage={setPage} 
          />
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
