"""
Email Service — sends OTP for password reset and username recovery
Uses smtplib with SMTP config from .env
Gracefully handles misconfigured SMTP (logs OTP/info to console in dev mode)
"""

import os
import smtplib
import random
import string
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional
from config import settings

logger = logging.getLogger("uvicorn.error")
# ... (otp stores remain same)
_otp_store: dict[str, dict] = {}           # password reset OTPs
_username_otp_store: dict[str, dict] = {}  # username recovery OTPs
_profile_otp_store: dict[str, dict] = {}   # profile update OTPs

OTP_EXPIRE_MINUTES = 10


# ──────────────────────────────────────────────────────────────────────────────
# OTP Generation & Storage (Existing logic remains)
# ──────────────────────────────────────────────────────────────────────────────

def generate_otp() -> str:
    """Generate a secure 6-digit numeric OTP"""
    return "".join(random.choices(string.digits, k=6))


def store_otp(email: str, code: str) -> None:
    """Store OTP with expiry timestamp"""
    _otp_store[email.lower()] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        "attempts": 0,
    }


def verify_otp(email: str, code: str) -> bool:
    """Verify OTP code — returns True if valid, deletes on success"""
    entry = _otp_store.get(email.lower())
    if not entry:
        return False

    # Check expiry
    if datetime.utcnow() > entry["expires_at"]:
        del _otp_store[email.lower()]
        return False

    # Increment attempt counter (max 5 attempts)
    entry["attempts"] += 1
    if entry["attempts"] > 5:
        del _otp_store[email.lower()]
        return False

    if entry["code"] == code:
        del _otp_store[email.lower()]
        return True

    return False


def invalidate_otp(email: str) -> None:
    """Remove OTP from store"""
    _otp_store.pop(email.lower(), None)


# ──────────────────────────────────────────────────────────────────────────────
# Unified Email Helper
# ──────────────────────────────────────────────────────────────────────────────

def _send_email_base(to_email: str, subject: str, html_content: str, fallback_label: str, otp_code: str) -> bool:
    """Core email sending logic with SMTP and Dev fallback"""
    
    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD
    sender = settings.SMTP_FROM

    # Dev mode fallback — print to console if SMTP not configured properly
    if not host or not user or user == "your-email@gmail.com":
        logger.warning(
            f"⚠️  SMTP not configured. DEV MODE — {fallback_label} OTP for {to_email}: [{otp_code}]"
        )
        print(f"\n{'='*60}")
        print(f"📧 [DEV EMAIL FALLBACK] — {fallback_label}")
        print(f"   Recipient : {to_email}")
        print(f"   Subject   : {subject}")
        print(f"   OTP Code  : {otp_code}")
        print(f"   Expiry    : {OTP_EXPIRE_MINUTES} minutes")
        print(f"{'='*60}\n")
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_email], msg.as_string())
        logger.info(f"✅ Email '{subject}' successfully sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"❌ SMTP Error sending to {to_email}: {str(e)}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Public Send Functions
# ──────────────────────────────────────────────────────────────────────────────

def send_password_reset_email(to_email: str, otp_code: str) -> bool:
    """Send OTP password reset email with professional HTML template"""
    
    subject = "Migration Intelligence — Password Reset Code"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Inter', Helvetica, Arial, sans-serif; background-color: #f9fafb; margin: 0; padding: 40px 0;">
      <div style="max-width: 500px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);">
        <div style="background-color: #2563eb; padding: 32px; text-align: center;">
          <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.025em;">Migration Intelligence</h1>
        </div>
        <div style="padding: 40px;">
          <h2 style="color: #111827; font-size: 20px; font-weight: 700; margin-bottom: 16px;">Password Reset Request</h2>
          <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin-bottom: 32px;">
            We received a request to reset the password for your account. Please use the following 6-digit verification code:
          </p>
          <div style="background-color: #f3f4f6; border: 2px solid #e5e7eb; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 32px;">
            <span style="font-family: 'Courier New', monospace; font-size: 42px; font-weight: 800; letter-spacing: 12px; color: #1d4ed8;">{otp_code}</span>
          </div>
          <p style="color: #6b7280; font-size: 14px; line-height: 20px;">
            This code is valid for <strong>{OTP_EXPIRE_MINUTES} minutes</strong>. If you did not request this change, you can safely ignore this email.
          </p>
          <div style="margin-top: 40px; padding-top: 24px; border-top: 1px solid #e5e7eb; text-align: center;">
            <p style="color: #9ca3af; font-size: 12px; margin: 0;">
              &copy; {datetime.now().year} Interlace Data Analyst &bull; Migration Intelligence Platform
            </p>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    
    return _send_email_base(to_email, subject, html_body, "Password Reset", otp_code)


def store_otp_for_username(email: str, code: str) -> None:
    """Store username-recovery OTP with expiry"""
    _username_otp_store[email.lower()] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        "attempts": 0,
    }


def verify_otp_for_username(email: str, code: str) -> bool:
    """Verify username-recovery OTP — returns True if valid, deletes on success"""
    entry = _username_otp_store.get(email.lower())
    if not entry:
        return False

    if datetime.utcnow() > entry["expires_at"]:
        del _username_otp_store[email.lower()]
        return False

    entry["attempts"] += 1
    if entry["attempts"] > 5:
        del _username_otp_store[email.lower()]
        return False

    if entry["code"] == code:
        del _username_otp_store[email.lower()]
        return True

    return False


def store_profile_otp(email: str, code: str) -> None:
    """Store OTP for profile update with expiry"""
    _profile_otp_store[email.lower()] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        "attempts": 0,
    }

def verify_profile_otp(email: str, code: str) -> bool:
    """Verify OTP code for profile update"""
    entry = _profile_otp_store.get(email.lower())
    if not entry:
        return False

    if datetime.utcnow() > entry["expires_at"]:
        del _profile_otp_store[email.lower()]
        return False

    entry["attempts"] += 1
    if entry["attempts"] > 5:
        del _profile_otp_store[email.lower()]
        return False

    if entry["code"] == code:
        del _profile_otp_store[email.lower()]
        return True

    return False


def send_profile_update_email(to_email: str, otp_code: str) -> bool:
    """Send profile update authorization OTP via SMTP"""
    subject = "Migration Intelligence - Authorize Profile Update"
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb; text-align: center;">Profile Update Request</h2>
        <p>You requested to update your profile (username or password) on the Migration Intelligence Platform.</p>
        <p>Please enter the following 6-digit verification code to authorize these changes:</p>
        
        <div style="background-color: #f3f4f6; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #1f2937;">{otp_code}</span>
        </div>
        
        <p style="font-size: 14px; color: #6b7280; text-align: center;">This code will expire in {OTP_EXPIRE_MINUTES} minutes.</p>
        
        <p style="margin-top: 30px;">If you did not request to update your profile, please ignore this email or contact the administrator immediately.</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;" />
        <p style="font-size: 12px; color: #9ca3af; text-align: center;">&copy; {datetime.utcnow().year} Migration Intelligence Platform. All rights reserved.</p>
      </body>
    </html>
    """
    
    return _send_email_base(to_email, subject, html_content, "Profile Update", otp_code)


def send_username_reveal_email(to_email: str, otp_code: str) -> bool:
    """Send OTP for username recovery with professional HTML template"""
    
    subject = "Migration Intelligence — Username Recovery Code"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Inter', Helvetica, Arial, sans-serif; background-color: #f9fafb; margin: 0; padding: 40px 0;">
      <div style="max-width: 500px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);">
        <div style="background-color: #059669; padding: 32px; text-align: center;">
          <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.025em;">Migration Intelligence</h1>
        </div>
        <div style="padding: 40px;">
          <h2 style="color: #111827; font-size: 20px; font-weight: 700; margin-bottom: 16px;">Username Recovery</h2>
          <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin-bottom: 32px;">
            To reveal your username, please verify your identity with the following 6-digit code:
          </p>
          <div style="background-color: #ecfdf5; border: 2px solid #d1fae5; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 32px;">
            <span style="font-family: 'Courier New', monospace; font-size: 42px; font-weight: 800; letter-spacing: 12px; color: #059669;">{otp_code}</span>
          </div>
          <p style="color: #6b7280; font-size: 14px; line-height: 20px;">
            This code is valid for <strong>{OTP_EXPIRE_MINUTES} minutes</strong>. If you did not request this, you can safely ignore this email.
          </p>
          <div style="margin-top: 40px; padding-top: 24px; border-top: 1px solid #e5e7eb; text-align: center;">
            <p style="color: #9ca3af; font-size: 12px; margin: 0;">
              &copy; {datetime.now().year} Interlace Data Analyst &bull; Migration Intelligence Platform
            </p>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    
    return _send_email_base(to_email, subject, html_body, "Username Recovery", otp_code)
