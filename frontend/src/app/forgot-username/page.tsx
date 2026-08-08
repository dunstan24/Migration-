"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

type Step = "email" | "verify" | "result";

export default function ForgotUsernamePage() {
  const router = useRouter();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [recoveredUsername, setRecoveredUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // ── Step 1: Request OTP ──────────────────────────────────────
  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/auth/forgot-username?email=${encodeURIComponent(email)}`,
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

  // ── Step 2: Verify OTP → get username ───────────────────────
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const code = otp.join("");
    if (code.length < 6) {
      setError("Please enter all 6 digits");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/auth/verify-username?email=${encodeURIComponent(email)}&otp_code=${encodeURIComponent(code)}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Invalid or expired verification code");
        if (data.detail?.includes("Invalid") || data.detail?.includes("expired")) {
          setOtp(["", "", "", "", "", ""]);
        }
        return;
      }
      const data = await res.json();
      setRecoveredUsername(data.username);
      setStep("result");
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── OTP input helpers ────────────────────────────────────────
  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d?$/.test(value)) return;
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    if (value && index < 5) {
      document.getElementById(`uotp-${index + 1}`)?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      document.getElementById(`uotp-${index - 1}`)?.focus();
    }
  };

  const handleOtpPaste = (e: React.ClipboardEvent) => {
    const paste = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (paste.length > 0) {
      const newOtp = paste.split("").concat(Array(6).fill("")).slice(0, 6);
      setOtp(newOtp);
      document.getElementById(`uotp-${Math.min(paste.length, 5)}`)?.focus();
    }
  };

  // ── Step indicator ───────────────────────────────────────────
  const steps = [
    { id: "email", label: "Email" },
    { id: "verify", label: "Verify" },
    { id: "result", label: "Username" },
  ];
  const stepIndex = steps.findIndex((s) => s.id === step);

  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center px-4 transition-colors duration-300">
      <div className="bg-[var(--surface)] rounded-2xl shadow-xl p-8 w-full max-w-md border border-[var(--border)] transition-colors duration-300">
        {/* Header */}
        <div className="mb-6 text-center">
          <h1 className="text-3xl font-bold text-[var(--text)]">Migration Intelligence</h1>
          <p className="text-[var(--muted)] mt-2">Recover your username</p>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center mb-8">
          {steps.map((s, i) => (
            <div key={s.id} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all
                    ${i < stepIndex
                      ? "bg-green-600 text-white"
                      : i === stepIndex
                      ? "bg-green-600 text-white ring-4 ring-green-500/20"
                      : "bg-[var(--bg)] text-[var(--muted)] border border-[var(--border)]"
                    }`}
                >
                  {i < stepIndex ? "✓" : i + 1}
                </div>
                <span
                  className={`text-[10px] mt-1 font-bold uppercase tracking-wider ${
                    i <= stepIndex ? "text-green-500" : "text-[var(--muted)]"
                  }`}
                >
                  {s.label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mb-5 mx-2 transition-all ${
                    i < stepIndex ? "bg-green-600" : "bg-[var(--border)]"
                  }`}
                />
              )}
            </div>
          ))}
        </div>

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
                className="w-full px-4 py-2.5 bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500/50 focus:border-green-500 disabled:opacity-50 transition-all"
              />
              <p className="text-[11px] text-[var(--muted)] mt-2 font-medium">
                We&apos;ll send a 6-digit code to verify your identity.
              </p>
            </div>
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full bg-green-600 text-white py-3 rounded-xl font-bold hover:bg-green-700 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-green-500/20"
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
                    id={`uotp-${i}`}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleOtpChange(i, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(i, e)}
                    className="w-11 h-12 text-center text-xl font-bold bg-[var(--bg)] text-[var(--text)] border-2 border-[var(--border)] rounded-xl
                               focus:outline-none focus:border-green-500 focus:ring-4 focus:ring-green-500/10
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
              disabled={loading || otp.join("").length < 6}
              className="w-full bg-green-600 text-white py-3 rounded-xl font-bold hover:bg-green-700 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-green-500/20"
            >
              {loading ? "Verifying..." : "Verify & Reveal Username"}
            </button>
            <button
              type="button"
              onClick={() => {
                setStep("email");
                setOtp(["", "", "", "", "", ""]);
                setError("");
              }}
              className="w-full text-xs text-green-500 hover:text-green-600 font-bold uppercase tracking-wider"
            >
              ← Use a different email
            </button>
          </form>
        )}

        {/* ── STEP 3: Result ──────────────────────────────────── */}
        {step === "result" && (
          <div className="text-center space-y-6 py-2">
            <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto border-2 border-green-500/20">
              <span className="text-4xl">👤</span>
            </div>
            <div>
              <p className="text-sm text-[var(--muted)] mb-3">
                Your username for <br/>
                <span className="font-bold text-[var(--text)]">{email}</span> is:
              </p>
              <div className="bg-[var(--bg)] border-2 border-[var(--border)] rounded-2xl py-5 px-6 shadow-inner">
                <span className="text-3xl font-black text-green-500 font-mono tracking-wider">
                  {recoveredUsername}
                </span>
              </div>
              <p className="text-[11px] text-[var(--muted)] mt-4 font-medium italic">
                Please keep your username safe.
              </p>
            </div>
            <div className="space-y-3 pt-2">
              <button
                onClick={() => router.push("/login")}
                className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 active:scale-[0.98] transition-all shadow-lg shadow-blue-500/20"
              >
                Go to Sign In
              </button>
              <button
                onClick={() => router.push("/forgot-password")}
                className="text-xs text-[var(--muted)] hover:text-blue-500 transition font-bold uppercase tracking-wider"
              >
                Forgot password? Reset it →
              </button>
            </div>
          </div>
        )}

        {/* Footer link */}
        {step !== "result" && (
          <div className="mt-8 pt-6 border-t border-[var(--border)] text-center">
            <Link
              href="/login"
              className="text-[10px] text-[var(--muted)] hover:text-blue-500 font-black uppercase tracking-widest transition-colors"
            >
              ← Back to Sign In
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
