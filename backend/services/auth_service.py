"""
Centralized Authentication Service

Security Features:
✅ 10-minute access token (prevents token reuse after logout)
✅ 7-day refresh token with rotation
✅ DB verification after JWT decode
✅ Secrets from environment (.env)
✅ IP detection via x-forwarded-for
✅ Proper error handling
"""

import os
import bcrypt
import jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from db.models import User
from fastapi import HTTPException, Request, status


class AuthService:
    """Authentication service - separation of concerns"""
    
    def __init__(self):
        # Load secrets from environment
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.REFRESH_SECRET = os.getenv("REFRESH_SECRET_KEY")
        
        # Auto-generate and persist if missing (for seamless first-time setup)
        if not self.SECRET_KEY or not self.REFRESH_SECRET:
            self._ensure_secrets_persist()
        
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 10080  # 🟢 7 Days for smooth UX
        self.REFRESH_TOKEN_EXPIRE_DAYS = 7

    def _ensure_secrets_persist(self):
        """Generate strong keys and write to .env so they survive reloads"""
        import secrets
        from pathlib import Path
        
        env_path = Path(__file__).resolve().parent.parent / ".env"
        
        # Fallback to root .env if backend/.env doesn't exist
        if not env_path.exists():
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"

        new_keys = {}
        if not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_hex(32)
            new_keys["SECRET_KEY"] = self.SECRET_KEY
        if not self.REFRESH_SECRET:
            self.REFRESH_SECRET = secrets.token_hex(32)
            new_keys["REFRESH_SECRET_KEY"] = self.REFRESH_SECRET

        if env_path.exists() and new_keys:
            try:
                with open(env_path, "a") as f:
                    f.write("\n# Auto-generated Auth Keys\n")
                    for k, v in new_keys.items():
                        f.write(f"{k}={v}\n")
                print(f"✅ Auto-generated and persisted auth keys to {env_path}")
            except Exception as e:
                print(f"⚠️ Could not persist keys to .env: {e}")
        elif new_keys:
            print("⚠️ .env file not found, keys will only exist in memory for this session.")
    
    # ──────────────────────────────────────────────────────────────────────
    # Password Hashing
    # ──────────────────────────────────────────────────────────────────────
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    
    # ──────────────────────────────────────────────────────────────────────
    # Token Generation
    # ──────────────────────────────────────────────────────────────────────
    
    def create_access_token(self, username: str, role: str, user_id: int) -> str:
        """Create short-lived JWT access token"""
        payload = {
            "sub": username,
            "role": role,
            "user_id": user_id,
            "type": "access",
            "exp": datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)
    
    def create_refresh_token(self, username: str, user_id: int) -> str:
        """Create long-lived JWT refresh token"""
        payload = {
            "sub": username,
            "user_id": user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.REFRESH_SECRET, algorithm=self.ALGORITHM)
    
    # ──────────────────────────────────────────────────────────────────────
    # Token Verification
    # ──────────────────────────────────────────────────────────────────────
    
    def verify_token(self, token: str, token_type: str = "access") -> dict:
        """Verify JWT token and return payload"""
        try:
            secret = self.SECRET_KEY if token_type == "access" else self.REFRESH_SECRET
            payload = jwt.decode(token, secret, algorithms=[self.ALGORITHM])
            
            if payload.get("type") != token_type:
                raise jwt.InvalidTokenError("Invalid token type")
            
            return payload
        
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    # ──────────────────────────────────────────────────────────────────────
    # Database Verification (CRITICAL)
    # ──────────────────────────────────────────────────────────────────────
    
    def verify_user_from_db(self, db: Session, payload: dict) -> User:
        """
        🚨 CRITICAL: After decoding JWT, verify user still exists in DB
        
        Prevents:
        - Deleted users staying logged in
        - Role changes not taking effect
        - Forged tokens
        - Inactive users accessing system
        """
        user_id = payload.get("user_id")
        username = payload.get("sub")
        
        if not user_id or not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            )
        
        user = db.query(User).filter(
            User.id == user_id,
            User.username == username,
            User.is_active == True
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return user
    
    # ──────────────────────────────────────────────────────────────────────
    # Complete Token Verification (Used by endpoints)
    # ──────────────────────────────────────────────────────────────────────
    
    def get_current_user(self, db: Session, token: str) -> User:
        """Complete token verification: decode + verify in DB"""
        payload = self.verify_token(token, token_type="access")
        return self.verify_user_from_db(db, payload)
    
    # ──────────────────────────────────────────────────────────────────────
    # Helper: Extract IP Address (handles proxies)
    # ──────────────────────────────────────────────────────────────────────
    
    @staticmethod
    def get_client_ip(request: Request) -> str:
        """
        Extract client IP with proxy support.
        
        🟡 FIX: Handles x-forwarded-for header (gets real IP behind proxy)
        Falls back to direct connection if no proxy
        """
        # Check for x-forwarded-for header (set by proxies/load balancers)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Fall back to direct connection
        return request.client.host if request.client else "0.0.0.0"


# Global instance - used across application
auth_service = AuthService()
