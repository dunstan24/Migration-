"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

type Step = "email" | "verify" | "reset" | "done";

export default function ForgotPasswordPage() {
  const router = useRouter();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // ── Step 1: Request OTP ──────────────────────────────────────
  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/auth/forgot-password?email=${encodeURIComponent(email)}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to send verification code");
        return;
      }
      setStep("verify");
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2: Verify OTP ───────────────────────────────────────
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const code = otp.join("");
    if (code.length < 6) {
      setError("Please enter all 6 digits");
      return;
    }
    // We just move to step 3 — actual verification happens on reset
    setError("");
    setStep("reset");
  };

  // ── Step 3: Reset Password ───────────────────────────────────
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      const code = otp.join("");
      const res = await fetch(
        `http://127.0.0.1:8000/api/auth/reset-password?email=${encodeURIComponent(email)}&otp_code=${encodeURIComponent(code)}&new_password=${encodeURIComponent(newPassword)}`,
        { method: "POST" }
      );

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to reset password");
        // If OTP invalid, go back to verify step
        if (data.detail?.includes("Invalid") || data.detail?.includes("expired")) {
          setStep("verify");
          setOtp(["", "", "", "", "", ""]);
        }
        return;
      }

      setStep("done");
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── OTP input handler ────────────────────────────────────────
  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d?$/.test(value)) return;
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    // Auto-focus next
    if (value && index < 5) {
      const next = document.getElementById(`otp-${index + 1}`);
      next?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      const prev = document.getElementById(`otp-${index - 1}`);
      prev?.focus();
    }
  };

  const handleOtpPaste = (e: React.ClipboardEvent) => {
    const paste = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (paste.length > 0) {
      const newOtp = paste.split("").concat(Array(6).fill("")).slice(0, 6);
      setOtp(newOtp);
      const last = document.getElementById(`otp-${Math.min(paste.length, 5)}`);
      last?.focus();
    }
  };

  // ── Step indicator ───────────────────────────────────────────
  const steps = [
    { id: "email", label: "Email" },
    { id: "verify", label: "Verify" },
    { id: "reset", label: "New Password" },
  ];
  const stepIndex = steps.findIndex((s) => s.id === step);

  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center px-4 transition-colors duration-300">
      <div className="bg-[var(--surface)] rounded-2xl shadow-xl p-8 w-full max-w-md border border-[var(--border)] transition-colors duration-300">
        {/* Header */}
        <div className="mb-6 text-center">
          <h1 className="text-3xl font-bold text-[var(--text)]">Migration Intelligence</h1>
          <p className="text-[var(--muted)] mt-2">Reset your password</p>
        </div>

        {/* Progress Steps */}
        {step !== "done" && (
          <div className="flex items-center mb-8">
            {steps.map((s, i) => (
              <div key={s.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all
                      ${i < stepIndex
                        ? "bg-blue-600 text-white"
                        : i === stepIndex
                        ? "bg-blue-600 text-white ring-4 ring-blue-500/20"
                        : "bg-[var(--bg)] text-[var(--muted)] border border-[var(--border)]"
                      }`}
                  >
                    {i < stepIndex ? "✓" : i + 1}
                  </div>
                  <span
                    className={`text-[10px] mt-1 font-bold uppercase tracking-wider ${
                      i <= stepIndex ? "text-blue-500" : "text-[var(--muted)]"
                    }`}
                  >
                    {s.label}
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <div
                    className={`flex-1 h-0.5 mb-5 mx-2 transition-all ${
                      i < stepIndex ? "bg-blue-600" : "bg-[var(--border)]"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-5 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
            <p className="text-red-500 text-sm font-medium">❌ {error}</p>
          </div>
        )}

        {/* ── STEP 1: Email ───────────────────────────────────── */}
        {step === "email" && (
          <form onSubmit={handleRequestOtp} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-[var(--text)] mb-2">
                Registered Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your registered email"
                required
                disabled={loading}
                className="w-full px-4 py-2.5 bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 disabled:opacity-50 transition-all"
              />
              <p className="text-[11px] text-[var(--muted)] mt-2 font-medium">
                We&apos;ll send a 6-digit verification code to this email.
              </p>
            </div>
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/20"
            >
              {loading ? "Sending code..." : "Send Verification Code"}
            </button>
          </form>
        )}

        {/* ── STEP 2: Verify OTP ──────────────────────────────── */}
        {step === "verify" && (
          <form onSubmit={handleVerifyOtp} className="space-y-5">
            <div>
              <p className="text-sm text-[var(--muted)] mb-4 text-center">
                We sent a 6-digit code to <br/>
                <span className="font-bold text-[var(--text)]">{email}</span>
              </p>
              <label className="block text-sm font-semibold text-[var(--text)] mb-3 text-center">
                Verification Code
              </label>
              <div className="flex gap-2 justify-between" onPaste={handleOtpPaste}>
                {otp.map((digit, i) => (
                  <input
                    key={i}
                    id={`otp-${i}`}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleOtpChange(i, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(i, e)}
                    className="w-11 h-12 text-center text-xl font-bold bg-[var(--bg)] text-[var(--text)] border-2 border-[var(--border)] rounded-xl
                               focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10
                                transition-all caret-transparent"
                  />
                ))}
              </div>
              <p className="text-[11px] text-[var(--muted)] mt-4 text-center font-medium">
                Code expires in 10 minutes. Check your spam folder.
              </p>
            </div>
            <button
              type="submit"
              disabled={otp.join("").length < 6}
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/20"
            >
              Verify Code
            </button>
            <button
              type="button"
              onClick={() => {
                setStep("email");
                setOtp(["", "", "", "", "", ""]);
                setError("");
              }}
              className="w-full text-xs text-blue-500 hover:text-blue-600 font-bold uppercase tracking-wider"
            >
              ← Use a different email
            </button>
          </form>
        )}

        {/* ── STEP 3: New Password ─────────────────────────────── */}
        {step === "reset" && (
          <form onSubmit={handleResetPassword} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-[var(--text)] mb-2">
                New Password
              </label>
              <div className="relative">
                <input
                  type={showNewPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password (6+ chars)"
                  required
                  disabled={loading}
                  className="w-full px-4 py-2.5 bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 disabled:opacity-50 transition-all pr-12"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-[var(--muted)] hover:text-[var(--text)] transition-colors"
                  tabIndex={-1}
                >
                  {showNewPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--text)] mb-2">
                Confirm New Password
              </label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your new password"
                  required
                  disabled={loading}
                  className="w-full px-4 py-2.5 bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 disabled:opacity-50 transition-all pr-12"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-[var(--muted)] hover:text-[var(--text)] transition-colors"
                  tabIndex={-1}
                >
                  {showConfirmPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
              {/* Password strength indicator */}
              {newPassword && (
                <div className="mt-3 flex gap-1">
                  {[...Array(4)].map((_, i) => (
                    <div
                      key={i}
                      className={`h-1 flex-1 rounded-full transition-all ${
                        newPassword.length >= (i + 1) * 3
                          ? newPassword.length >= 12
                            ? "bg-green-500"
                            : newPassword.length >= 8
                            ? "bg-yellow-400"
                            : "bg-red-400"
                          : "bg-[var(--border)]"
                      }`}
                    />
                  ))}
                </div>
              )}
            </div>
            <button
              type="submit"
              disabled={loading || !newPassword || !confirmPassword}
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/20 mt-4"
            >
              {loading ? "Resetting password..." : "Reset Password"}
            </button>
          </form>
        )}

        {/* ── STEP 4: Done ────────────────────────────────────── */}
        {step === "done" && (
          <div className="text-center space-y-6 py-4">
            <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto border-2 border-green-500/20">
              <span className="text-4xl">✅</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--text)]">Success!</h2>
              <p className="text-[var(--muted)] mt-2 text-sm">
                Your password has been successfully reset.
              </p>
            </div>
            <button
              onClick={() => router.push("/login")}
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 active:scale-[0.98] transition-all shadow-lg shadow-blue-500/20"
            >
              Back to Sign In
            </button>
          </div>
        )}

        {/* Footer link */}
        {step !== "done" && (
          <div className="mt-8 pt-6 border-t border-[var(--border)] text-center">
            <Link
              href="/login"
              className="text-xs text-[var(--muted)] hover:text-blue-500 font-bold uppercase tracking-widest transition-colors"
            >
              ← Back to Sign In
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
