"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useSession } from "next-auth/react";
import Cropper from "react-easy-crop";
import getCroppedImg from "@/lib/cropImage";

export default function ProfilePage() {
  const { data: session } = useSession();
  const [isEditing, setIsEditing] = useState(false);
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Edit states
  const [newUsername, setNewUsername] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  // OTP Modal states
  const [showOtpModal, setShowOtpModal] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [otpLoading, setOtpLoading] = useState(false);
  const [message, setMessage] = useState({ text: "", type: "" });

  // Cropper states
  const [imageToCrop, setImageToCrop] = useState<string | null>(null);
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<any>(null);
  const [showCropModal, setShowCropModal] = useState(false);

  const BACKEND_URL = "";

  const fetchProfile = async () => {
    if (!session?.user?.accessToken) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/profile`, {
        headers: {
          Authorization: `Bearer ${(session.user as any).accessToken}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setNewUsername(data.username);
      }
    } catch (err) {
      console.error("Error fetching profile:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, [session]);

  const handlePictureUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      setMessage({ text: "Image must be less than 2MB", type: "error" });
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      setImageToCrop(reader.result as string);
      setShowCropModal(true);
    };
    reader.readAsDataURL(file);
  };

  const onCropComplete = useCallback((_croppedArea: any, croppedAreaPixels: any) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  const handleCropSave = async () => {
    if (!imageToCrop || !croppedAreaPixels) return;

    setIsSaving(true);
    try {
      const croppedImageBase64 = await getCroppedImg(imageToCrop, croppedAreaPixels);
      
      // Update locally immediately for better UX
      setProfile({ ...profile, profile_picture: croppedImageBase64 });

      const res = await fetch(`${BACKEND_URL}/api/auth/profile/picture`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${(session?.user as any)?.accessToken}`,
        },
        body: JSON.stringify({ profile_picture: croppedImageBase64 }),
      });

      if (!res.ok) {
        const err = await res.json();
        const errorMsg = typeof err.detail === 'string' ? err.detail : Array.isArray(err.detail) ? err.detail[0]?.msg : "Failed to update picture";
        setMessage({ text: errorMsg, type: "error" });
        fetchProfile(); // revert
      } else {
        setMessage({ text: "Profile picture updated", type: "success" });
        window.dispatchEvent(new Event("profileUpdate"));
        setTimeout(() => setMessage({ text: "", type: "" }), 3000);
        setShowCropModal(false);
        setImageToCrop(null);
      }
    } catch (err) {
      console.error(err);
      setMessage({ text: "Error cropping image", type: "error" });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemovePicture = async () => {
    setProfile({ ...profile, profile_picture: "" });
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/profile/picture`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${(session?.user as any)?.accessToken}`,
        },
        body: JSON.stringify({ profile_picture: "" }),
      });

      if (res.ok) {
        setMessage({ text: "Profile picture removed", type: "success" });
        window.dispatchEvent(new Event("profileUpdate"));
        setTimeout(() => setMessage({ text: "", type: "" }), 3000);
      } else {
        fetchProfile();
      }
    } catch (err) {
      setMessage({ text: "Network error", type: "error" });
    }
  };

  const handleRequestSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword) {
      if (!oldPassword) {
        setMessage({ text: "Current password is required to set a new password", type: "error" });
        return;
      }
      if (newPassword !== confirmPassword) {
        setMessage({ text: "New passwords do not match", type: "error" });
        return;
      }
    }

    setIsSaving(true);
    
    // Skip OTP if only changing username
    if (!newPassword) {
      await submitOtpUpdate(true);
      return;
    }

    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/profile/request-otp`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${(session?.user as any)?.accessToken}`,
        },
      });

      if (res.ok) {
        setShowOtpModal(true);
        setMessage({ text: "OTP sent to your email", type: "success" });
      } else {
        const err = await res.json();
        const errorMsg = typeof err.detail === 'string' ? err.detail : Array.isArray(err.detail) ? err.detail[0]?.msg : "Failed to send OTP";
        setMessage({ text: errorMsg, type: "error" });
      }
    } catch (err) {
      setMessage({ text: "Network error", type: "error" });
    } finally {
      setIsSaving(false);
    }
  };

  const submitOtpUpdate = async (skipOtp: boolean = false) => {
    if (!skipOtp && otpCode.length !== 6) {
      setMessage({ text: "OTP must be 6 digits", type: "error" });
      return;
    }

    setOtpLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/profile/update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${(session?.user as any)?.accessToken}`,
        },
        body: JSON.stringify({
          otp_code: skipOtp ? null : otpCode,
          new_username: newUsername !== profile.username ? newUsername : null,
          old_password: oldPassword ? oldPassword : null,
          new_password: newPassword ? newPassword : null,
        }),
      });

      if (res.ok) {
        if (newPassword) {
          setMessage({ text: "Password changed successfully! Logging you out...", type: "success" });
          setTimeout(() => {
            import("next-auth/react").then(({ signOut }) => signOut());
          }, 1500);
          return;
        }

        setMessage({ text: "Profile updated successfully! Please re-login to sync session completely.", type: "success" });
        setShowOtpModal(false);
        setIsEditing(false);
        setOldPassword("");
        setNewPassword("");
        setConfirmPassword("");
        setOtpCode("");
        setIsSaving(false);
        window.dispatchEvent(new Event("profileUpdate"));
        fetchProfile();
      } else {
        const err = await res.json();
        const errorMsg = typeof err.detail === 'string' 
          ? err.detail 
          : Array.isArray(err.detail) 
            ? err.detail[0]?.msg 
            : "Failed to update profile";
        setMessage({ text: errorMsg, type: "error" });
      }
    } catch (err) {
      setMessage({ text: "Network error", type: "error" });
    } finally {
      setOtpLoading(false);
      setIsSaving(false);
    }
  };

  if (loading) {
    return <div style={{ padding: 40, color: "var(--text)" }}>Loading profile...</div>;
  }

  if (!profile) {
    return <div style={{ padding: 40, color: "var(--text)" }}>Failed to load profile.</div>;
  }

  return (
    <div style={{ padding: "40px 20px", maxWidth: 800, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text)" }}>My Profile</h1>
        {!isEditing ? (
          <button
            onClick={() => setIsEditing(true)}
            style={{
              padding: "8px 16px",
              background: "#2563eb",
              color: "white",
              border: "none",
              borderRadius: 8,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Edit Profile
          </button>
        ) : (
          <button
            onClick={() => setIsEditing(false)}
            style={{
              padding: "8px 16px",
              background: "var(--surface)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Cancel Edit
          </button>
        )}
      </div>

      {message.text && !showOtpModal && (
        <div
          style={{
            padding: 16,
            marginBottom: 24,
            borderRadius: 8,
            background: message.type === "success" ? "#ecfdf5" : "#fef2f2",
            color: message.type === "success" ? "#047857" : "#b91c1c",
            border: `1px solid ${message.type === "success" ? "#a7f3d0" : "#fecaca"}`,
          }}
        >
          {message.text}
        </div>
      )}

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16, overflow: "hidden" }}>
        {/* Banner */}
        <div style={{ height: 120, background: "linear-gradient(135deg, #2563eb, #8b5cf6)" }} />
        
        <div style={{ padding: 32, position: "relative", paddingTop: 0 }}>
          {/* Avatar */}
          <div style={{ display: "flex", alignItems: "flex-end", gap: 16, marginTop: -50, marginBottom: 24, flexWrap: "wrap" }}>
            <div 
              style={{ 
                width: 100, height: 100, borderRadius: "50%", 
                background: profile.profile_picture ? "var(--background)" : "#e0e7ff", 
                border: "4px solid var(--surface)",
                position: "relative",
                overflow: "hidden",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 32, fontWeight: 800, color: "#4f46e5"
              }}
            >
              {profile.profile_picture ? (
                <img src={profile.profile_picture} alt="Profile" style={{ width: "100%", height: "100%", objectFit: "cover", background: "white" }} />
              ) : (
                profile.username[0]?.toUpperCase()
              )}
              
              {isEditing && (
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    position: "absolute", inset: 0, background: "rgba(0,0,0,0.5)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "white", fontSize: 12, cursor: "pointer", fontWeight: 600,
                    opacity: 0, transition: "opacity 0.2s"
                  }}
                  onMouseEnter={e => e.currentTarget.style.opacity = "1"}
                  onMouseLeave={e => e.currentTarget.style.opacity = "0"}
                >
                  Change
                </div>
              )}
              <input 
                type="file" accept="image/*" ref={fileInputRef} 
                style={{ display: "none" }} onChange={handlePictureUpload}
              />
            </div>
            
            {isEditing && profile.profile_picture && (
              <button
                type="button"
                onClick={handleRemovePicture}
                style={{
                  marginBottom: 8, padding: "6px 12px", fontSize: 12, fontWeight: 600,
                  color: "#ef4444", background: "var(--surface)", border: "1px solid var(--border)",
                  borderRadius: 6, cursor: "pointer"
                }}
              >
                Remove Picture
              </button>
            )}
          </div>

          {!isEditing ? (
            /* VIEW MODE */
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              <div>
                <p style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>Username</p>
                <p style={{ fontSize: 16, color: "var(--text)", fontWeight: 500 }}>{profile.username}</p>
              </div>
              <div>
                <p style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>Email</p>
                <p style={{ fontSize: 16, color: "var(--text)", fontWeight: 500 }}>{profile.email}</p>
              </div>
              <div>
                <p style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>Role</p>
                <span style={{ 
                  display: "inline-block", padding: "4px 12px", borderRadius: 100, fontSize: 12, fontWeight: 700,
                  background: profile.role === "superadmin" ? "#f3e8ff" : profile.role === "admin" ? "#dbeafe" : "#f1f5f9",
                  color: profile.role === "superadmin" ? "#7e22ce" : profile.role === "admin" ? "#1d4ed8" : "#475569"
                }}>
                  {profile.role.toUpperCase()}
                </span>
              </div>
            </div>
          ) : (
            /* EDIT MODE */
            <form onSubmit={handleRequestSave} style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: "100%" }}>
              <div>
                <label style={{ display: "block", fontSize: 13, color: "var(--muted)", fontWeight: 600, marginBottom: 6 }}>Username</label>
                <input
                  required
                  type="text"
                  value={newUsername}
                  onChange={e => setNewUsername(e.target.value)}
                  style={{
                    width: "100%", padding: "10px 14px", borderRadius: 8,
                    border: "1px solid var(--border)", background: "var(--background)", color: "var(--text)",
                    outline: "none", fontSize: 14
                  }}
                />
              </div>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <label style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>Current Password (required to change password)</label>
                  <a href="/forgot-password" style={{ fontSize: 11, color: "#2563eb", textDecoration: "none", fontWeight: 600 }}>Forgot Password?</a>
                </div>
                <div style={{ position: "relative" }}>
                  <input
                    type={showOldPassword ? "text" : "password"}
                    value={oldPassword}
                    onChange={e => setOldPassword(e.target.value)}
                    placeholder="••••••••"
                    style={{
                      width: "100%", padding: "10px 14px", paddingRight: "40px", borderRadius: 8,
                      border: "1px solid var(--border)", background: "var(--background)", color: "var(--text)",
                      outline: "none", fontSize: 14
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowOldPassword(!showOldPassword)}
                    style={{
                      position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)",
                      background: "none", border: "none", color: "var(--muted)", cursor: "pointer",
                      display: "flex", alignItems: "center", justifyContent: "center", padding: "4px"
                    }}
                    tabIndex={-1}
                  >
                    {showOldPassword ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
              {oldPassword && (
                <>
                  <div>
                    <label style={{ display: "block", fontSize: 13, color: "var(--muted)", fontWeight: 600, marginBottom: 6 }}>New Password</label>
                    <div style={{ position: "relative" }}>
                      <input
                        required
                        type={showNewPassword ? "text" : "password"}
                        value={newPassword}
                        onChange={e => setNewPassword(e.target.value)}
                        placeholder="••••••••"
                        style={{
                          width: "100%", padding: "10px 14px", paddingRight: "40px", borderRadius: 8,
                          border: "1px solid var(--border)", background: "var(--background)", color: "var(--text)",
                          outline: "none", fontSize: 14
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPassword(!showNewPassword)}
                        style={{
                          position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)",
                          background: "none", border: "none", color: "var(--muted)", cursor: "pointer",
                          display: "flex", alignItems: "center", justifyContent: "center", padding: "4px"
                        }}
                        tabIndex={-1}
                      >
                        {showNewPassword ? (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                            <line x1="1" y1="1" x2="23" y2="23" />
                          </svg>
                        ) : (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                            <circle cx="12" cy="12" r="3" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                  {newPassword && (
                    <div>
                      <label style={{ display: "block", fontSize: 13, color: "var(--muted)", fontWeight: 600, marginBottom: 6 }}>Confirm New Password</label>
                      <div style={{ position: "relative" }}>
                        <input
                          required
                          type={showConfirmPassword ? "text" : "password"}
                          value={confirmPassword}
                          onChange={e => setConfirmPassword(e.target.value)}
                          placeholder="••••••••"
                          style={{
                            width: "100%", padding: "10px 14px", paddingRight: "40px", borderRadius: 8,
                            border: "1px solid var(--border)", background: "var(--background)", color: "var(--text)",
                            outline: "none", fontSize: 14
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                          style={{
                            position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)",
                            background: "none", border: "none", color: "var(--muted)", cursor: "pointer",
                            display: "flex", alignItems: "center", justifyContent: "center", padding: "4px"
                          }}
                          tabIndex={-1}
                        >
                          {showConfirmPassword ? (
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                              <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                          ) : (
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                              <circle cx="12" cy="12" r="3" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
              
              <button
                type="submit"
                disabled={isSaving || (newUsername === profile.username && !newPassword)}
                style={{
                  marginTop: 10, padding: "12px", background: "#2563eb", color: "white",
                  border: "none", borderRadius: 8, fontWeight: 600, cursor: isSaving ? "wait" : "pointer",
                  opacity: (isSaving || (newUsername === profile.username && !newPassword)) ? 0.7 : 1
                }}
              >
                {isSaving ? "Requesting OTP..." : "Save Changes"}
              </button>
            </form>
          )}
        </div>
      </div>

      {/* OTP Modal */}
      {showOtpModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 100,
          display: "flex", alignItems: "center", justifyContent: "center"
        }}>
          <div style={{
            background: "var(--surface)", padding: 32, borderRadius: 16, width: 400,
            border: "1px solid var(--border)", boxShadow: "0 20px 40px rgba(0,0,0,0.2)"
          }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, color: "var(--text)", marginBottom: 8 }}>Verification Required</h3>
            <p style={{ fontSize: 14, color: "var(--muted)", marginBottom: 24 }}>
              We've sent a 6-digit code to your email. Please enter it below to authorize these changes.
            </p>

            {message.text && (
              <div style={{ marginBottom: 16, color: message.type === "success" ? "#10b981" : "#ef4444", fontSize: 13 }}>
                {message.text}
              </div>
            )}

            <input
              type="text"
              maxLength={6}
              value={otpCode}
              onChange={e => setOtpCode(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder="000000"
              style={{
                width: "100%", padding: "12px", borderRadius: 8, textAlign: "center", fontSize: 24, letterSpacing: 8,
                border: "1px solid var(--border)", background: "var(--background)", color: "var(--text)", outline: "none", marginBottom: 24
              }}
            />

            <div style={{ display: "flex", gap: 12 }}>
              <button
                onClick={() => setShowOtpModal(false)}
                style={{ flex: 1, padding: "10px", background: "var(--background)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, fontWeight: 600, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={() => submitOtpUpdate()}
                disabled={otpLoading || otpCode.length !== 6}
                style={{ flex: 1, padding: "10px", background: "#2563eb", color: "white", border: "none", borderRadius: 8, fontWeight: 600, cursor: "pointer", opacity: otpLoading || otpCode.length !== 6 ? 0.7 : 1 }}
              >
                {otpLoading ? "Verifying..." : "Verify & Save"}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Image Crop Modal */}
      {showCropModal && imageToCrop && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 200,
          display: "flex", alignItems: "center", justifyContent: "center", padding: 20
        }}>
          <div style={{
            background: "var(--surface)", padding: 24, borderRadius: 16, width: "100%", maxWidth: 500,
            display: "flex", flexDirection: "column", gap: 20
          }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, color: "var(--text)" }}>Crop Profile Picture</h3>
            
            <div style={{ position: "relative", width: "100%", height: 300, background: "#333", borderRadius: 8, overflow: "hidden" }}>
              <Cropper
                image={imageToCrop}
                crop={crop}
                zoom={zoom}
                aspect={1}
                cropShape="round"
                showGrid={false}
                onCropChange={setCrop}
                onCropComplete={onCropComplete}
                onZoomChange={setZoom}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <label style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Zoom</label>
              <input
                type="range"
                value={zoom}
                min={1}
                max={3}
                step={0.1}
                aria-labelledby="Zoom"
                onChange={(e) => setZoom(Number(e.target.value))}
                style={{ width: "100%", cursor: "pointer" }}
              />
            </div>

            <div style={{ display: "flex", gap: 12 }}>
              <button
                onClick={() => {
                  setShowCropModal(false);
                  setImageToCrop(null);
                }}
                style={{ flex: 1, padding: "10px", background: "var(--background)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, fontWeight: 600, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={handleCropSave}
                disabled={isSaving}
                style={{ flex: 1, padding: "10px", background: "#2563eb", color: "white", border: "none", borderRadius: 8, fontWeight: 600, cursor: isSaving ? "wait" : "pointer", opacity: isSaving ? 0.7 : 1 }}
              >
                {isSaving ? "Saving..." : "Crop & Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
