import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { C } from "@/components/ui";

interface User {
  user_id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string;
  failed_attempts_7d: number;
}

interface Activity {
  id: number;
  user_id: number;
  username: string;
  action: string;
  severity: string;
  timestamp: string;
  ip_address: string;
  status: string;
}

interface UserDetail {
  id: number;
  username: string;
  role: string;
  email: string;
}

export default function UsersTab() {
  const { data: session, status } = useSession();
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserDetail | null>(null);
  const [userActivity, setUserActivity] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activityLoading, setActivityLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [promoteLoading, setPromoteLoading] = useState(false);

  const API_PREFIX = "/api";

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await fetch(`${API_PREFIX}/admin/users`, {
          headers: {
            ...(session?.user?.accessToken && {
              Authorization: `Bearer ${session.user.accessToken}`,
            }),
          },
        });
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Failed to fetch users: ${response.status} ${errorText}`);
        }
        const data = await response.json();
        setUsers(data.users || []);
        setError("");
      } catch (err) {
        setError("Failed to load users");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    if (status === "authenticated") fetchUsers();
  }, [status, session]);

  const fetchUserActivity = async (userId: number) => {
    setActivityLoading(true);
    try {
      const response = await fetch(
        `${API_PREFIX}/admin/users/${userId}/activity`,
        {
          headers: {
            ...(session?.user?.accessToken && {
              Authorization: `Bearer ${session.user.accessToken}`,
            }),
          },
        }
      );
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to fetch activity: ${response.status} ${errorText}`);
      }
      const data = await response.json();
      setUserActivity(data.activities || []);
      if (data.user) {
        setSelectedUser({
          id: data.user.id,
          username: data.user.username,
          role: data.user.role,
          email: data.user.email || "",
        });
      }
    } catch (err) {
      console.error(err);
      setUserActivity([]);
    } finally {
      setActivityLoading(false);
    }
  };

  const deleteUser = async (userId: number) => {
    if (!window.confirm("Are you sure you want to delete this user?")) {
      return;
    }

    setDeleteLoading(true);
    try {
      const response = await fetch(`${API_PREFIX}/admin/users/${userId}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          ...(session?.user?.accessToken && {
            Authorization: `Bearer ${session.user.accessToken}`,
          }),
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to delete user: ${response.status} ${errorText}`);
      }

      setUsers((prev) => prev.filter((user) => user.user_id !== userId));
      setSelectedUser(null);
      setUserActivity([]);
      setError("");
    } catch (err) {
      console.error(err);
      setError("Failed to delete user");
    } finally {
      setDeleteLoading(false);
    }
  };

  const promoteUser = async (userId: number) => {
    if (!window.confirm("Promote this user to admin?")) {
      return;
    }

    setPromoteLoading(true);
    try {
      const response = await fetch(`${API_PREFIX}/admin/users/${userId}/promote`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(session?.user?.accessToken && {
            Authorization: `Bearer ${session.user.accessToken}`,
          }),
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to promote user: ${response.status} ${errorText}`);
      }

      const data = await response.json();
      setSelectedUser((prev) => prev ? { ...prev, role: "admin" } : prev);
      setUsers((prev) => prev.map((user) => user.user_id === userId ? { ...user, role: "admin" } : user));
      setError("");
    } catch (err) {
      console.error(err);
      setError("Failed to promote user");
    } finally {
      setPromoteLoading(false);
    }
  };

  const handleSelectUser = (user: User) => {
    setSelectedUser({ id: user.user_id, username: user.username, role: user.role, email: "" });
    fetchUserActivity(user.user_id);
  };

  if (status === "loading" || loading) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center", color: C.muted, fontSize: 13 }}>
        <div style={{ width: 24, height: 24, border: `2px solid var(--border)`, borderTopColor: C.blue, borderRadius: "50%", margin: "0 auto 12px", animation: "spin 0.8s linear infinite" }} />
        Loading users...
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <div style={{ margin: "16px 0" }}>
      {error && (
        <div style={{ marginBottom: 20, padding: "12px 16px", background: `${C.red}15`, border: `1px solid ${C.red}35`, borderRadius: 10, color: C.red, fontSize: 13 }}>
          {error}
        </div>
      )}

      <div style={{ 
        display: "grid", 
        gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", 
        gap: 20 
      }}>
        {/* ── Users List ──────────────────────────────────────── */}
        <div style={{ background: "var(--surface)", border: `1px solid var(--border)`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: `1px solid var(--border)` }}>
            <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>
              Users ({users.length})
            </p>
          </div>
          <div style={{ maxHeight: 480, overflowY: "auto" }}>
            {users.length === 0 ? (
              <p style={{ padding: 16, fontSize: 13, color: C.muted }}>No users found</p>
            ) : (
              users.map((user) => {
                const isSelected = selectedUser?.id === user.user_id;
                return (
                  <button
                    key={user.user_id}
                    onClick={() => handleSelectUser(user)}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "14px 20px",
                      borderLeft: `3px solid ${isSelected ? C.blue : "transparent"}`,
                      borderTop: "none",
                      borderRight: "none",
                      borderBottom: `1px solid var(--border)`,
                      background: isSelected ? `${C.blue}10` : "transparent",
                      cursor: "pointer",
                      transition: "background 0.15s",
                      display: "block",
                    }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", marginBottom: 3 }}>
                      {user.username}
                    </div>
                    <div style={{ fontSize: 11, color: C.muted }}>
                      {user.role === "superadmin" ? "👑 Super Admin" : user.role === "admin" ? "🛡️ Administrator" : "👤 Regular User"}
                    </div>
                    {!user.is_active && (
                      <div style={{ fontSize: 11, color: C.red, marginTop: 2 }}>Inactive</div>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* ── User Details + Activity ─────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {selectedUser ? (
            <>
              {/* User Info Card */}
              <div style={{ background: "var(--surface)", border: `1px solid var(--border)`, borderRadius: 12, overflow: "hidden" }}>
                <div style={{ padding: "12px 20px", borderBottom: `1px solid var(--border)`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>User Details</p>
                  {session?.user?.id !== String(selectedUser.id) && (
                    <div style={{ display: "flex", gap: 8 }}>
                      {selectedUser.role === "user" && (
                        <button
                          type="button"
                          disabled={promoteLoading}
                          onClick={() => promoteUser(selectedUser.id)}
                          style={{
                            minHeight: 28,
                            padding: "0 12px",
                            borderRadius: 6,
                            border: "1px solid #2563eb",
                            background: promoteLoading ? "var(--surface)" : "var(--surface)",
                            color: "#1d4ed8",
                            cursor: promoteLoading ? "not-allowed" : "pointer",
                            fontWeight: 700,
                            fontSize: 11,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          {promoteLoading ? "..." : "Make Admin"}
                        </button>
                      )}
                      
                      {/* Hide Delete button if target is superadmin AND current user is not superadmin */}
                      {!(selectedUser.role === "superadmin" && (session?.user as any)?.role !== "superadmin") && (
                        <button
                          type="button"
                          disabled={deleteLoading}
                          onClick={() => deleteUser(selectedUser.id)}
                          style={{
                            minHeight: 28,
                            padding: "0 12px",
                            borderRadius: 6,
                            border: "1px solid #f87171",
                            background: deleteLoading ? "var(--surface)" : "var(--surface)",
                            color: "#b91c1c",
                            cursor: deleteLoading ? "not-allowed" : "pointer",
                            fontWeight: 700,
                            fontSize: 11,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          {deleteLoading ? "..." : "Delete User"}
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <div style={{ padding: "20px" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    {[
                      { label: "Username", value: selectedUser.username },
                      { label: "User ID", value: String(selectedUser.id) },
                      { label: "Email", value: selectedUser.email || "-" },
                    ].map((item) => (
                      <div key={item.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 13, color: C.muted }}>{item.label}:</span>
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{item.value}</span>
                      </div>
                    ))}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 13, color: C.muted }}>Role:</span>
                      <span style={{
                        fontSize: 11,
                        fontWeight: 700,
                        padding: "3px 10px",
                        borderRadius: 6,
                        background: selectedUser.role === "superadmin" ? `${C.purple}20` : selectedUser.role === "admin" ? `${C.blue}20` : "var(--bg)",
                        color: selectedUser.role === "superadmin" ? C.purple : selectedUser.role === "admin" ? C.blue : C.muted,
                        border: `1px solid ${selectedUser.role === "superadmin" ? C.purple : selectedUser.role === "admin" ? C.blue : "var(--border)"}40`,
                      }}>
                        {selectedUser.role.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recent Activity */}
              <div style={{ background: "var(--surface)", border: `1px solid var(--border)`, borderRadius: 12, overflow: "hidden" }}>
                <div style={{ padding: "16px 20px", borderBottom: `1px solid var(--border)` }}>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>Recent Activity</p>
                </div>
                {activityLoading ? (
                  <p style={{ padding: "32px", textAlign: "center", color: C.muted, fontSize: 13 }}>Loading activity...</p>
                ) : userActivity.length === 0 ? (
                  <p style={{ padding: "32px", textAlign: "center", color: C.muted, fontSize: 13 }}>No activity recorded</p>
                ) : (
                  <div style={{ overflowX: "auto", maxHeight: "300px" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead>
                        <tr style={{ background: "var(--surface-alt)", borderBottom: `1px solid var(--border)` }}>
                          {["Action", "Status", "Timestamp", "IP Address"].map((h) => (
                            <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: 10, fontWeight: 700, color: C.muted, textTransform: "uppercase", letterSpacing: "0.07em", position: "sticky", top: 0, background: "var(--surface-alt)" }}>
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {userActivity.map((activity, i) => {
                          const okColor = activity.status === "success" ? C.green : C.red;
                          return (
                            <tr key={activity.id} style={{ borderBottom: `1px solid var(--border)`, background: i % 2 === 0 ? "transparent" : "var(--surface-alt)" }}>
                              <td style={{ padding: "12px 20px", fontSize: 13, fontWeight: 600, color: "var(--text)", textTransform: "capitalize" }}>
                                {activity.action}
                              </td>
                              <td style={{ padding: "12px 20px" }}>
                                <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, background: `${okColor}20`, color: okColor, border: `1px solid ${okColor}40` }}>
                                  {activity.status}
                                </span>
                              </td>
                              <td style={{ padding: "12px 20px", fontSize: 12, color: C.muted }}>
                                {new Date(activity.timestamp).toLocaleString()}
                              </td>
                              <td style={{ padding: "12px 20px", fontSize: 12, fontFamily: "monospace", color: C.muted }}>
                                {activity.ip_address}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ background: "var(--surface)", border: `1px solid var(--border)`, borderRadius: 12, padding: "64px 32px", textAlign: "center" }}>
              <p style={{ fontSize: 13, color: C.muted }}>
                Select a user from the list to view details and activity logs
              </p>
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
