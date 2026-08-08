"""
Authentication Router
Handles login, logout, register, and token refresh
All endpoints include activity logging and rate limiting
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.database import get_sync_db
from db.models import User
from services.auth_service import auth_service
from services.activity_service import activity_service
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging
import secrets
import string

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger("uvicorn.error")

# ──────────────────────────────────────────────────────────────────────────
# Dependency: Get Current User (used by protected endpoints)
# ──────────────────────────────────────────────────────────────────────────

def get_current_user(request: Request, db: Session = Depends(get_sync_db)) -> User:
    """Extract and verify JWT token from Authorization header"""
    
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header.split(" ")[1]
    return auth_service.get_current_user(db, token)


# ──────────────────────────────────────────────────────────────────────────
# POST /api/auth/login
# ──────────────────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("5/minute") if limiter else lambda f: f  # 🚨 Rate limit: 5 attempts per minute
async def login(
    username: str,
    password: str,
    request: Request,
    db: Session = Depends(get_sync_db)
):
    """
    Authenticate user and return JWT tokens
    
    Rate limited: 5 attempts per minute per IP
    Logs: all attempts (success and failure)
    """
    
    client_ip = auth_service.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:200]
    
    # Find user
    user = db.query(User).filter(User.username == username).first()
    
    # Failed: user doesn't exist
    if not user:
        activity_service.log_activity(
            db=db,
            user_id=None,
            action="login",
            ip_address=client_ip,
            user_agent=user_agent,
            status="failed",
            severity="warning",
            details=f"User not found: {username}"
        )
        
        logger.warning(f"❌ Failed login attempt: user '{username}' not found from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Failed: wrong password
    if not auth_service.verify_password(password, user.password_hash):
        activity_service.log_activity(
            db=db,
            user_id=user.id,
            action="login",
            ip_address=client_ip,
            user_agent=user_agent,
            status="failed",
            severity="warning",
            details="Invalid password"
        )
        
        logger.warning(f"❌ Failed login attempt: wrong password for '{username}' from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Failed: user inactive
    if not user.is_active:
        activity_service.log_activity(
            db=db,
            user_id=user.id,
            action="login",
            ip_address=client_ip,
            user_agent=user_agent,
            status="failed",
            severity="critical",
            details="Account inactive"
        )
        
        logger.warning(f"❌ Failed login: account inactive for '{username}' from {client_ip}")
        raise HTTPException(status_code=403, detail="Account inactive")
    
    # Success: log login
    activity_service.log_activity(
        db=db,
        user_id=user.id,
        action="login",
        ip_address=client_ip,
        user_agent=user_agent,
        status="success",
        severity="info"
    )
    
    logger.info(f"✅ Successful login: '{username}' from {client_ip}")
    
    # Create tokens
    access_token = auth_service.create_access_token(
        username=user.username,
        role=user.role,
        user_id=user.id
    )
    refresh_token = auth_service.create_refresh_token(
        username=user.username,
        user_id=user.id
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 604800,  # 10 minutes in seconds
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email
        }
    }


# ──────────────────────────────────────────────────────────────────────────
# POST /api/auth/google
# ──────────────────────────────────────────────────────────────────────────

class GoogleLoginRequest(BaseModel):
    email: str
    name: str


@router.post("/google")
@limiter.limit("10/minute") if limiter else lambda f: f
async def google_login(
    payload: GoogleLoginRequest,
    request: Request,
    db: Session = Depends(get_sync_db)
):
    """
    Handle Google OAuth2 Login
    Creates a new user if the email doesn't exist.
    Returns standard JWT tokens.
    """
    
    client_ip = auth_service.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:200]
    
    email = payload.email
    name = payload.name
    
    # Check if user exists
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Create new user for Google login
        # Generate a random password since they will use Google to login
        alphabet = string.ascii_letters + string.digits + string.punctuation
        random_password = ''.join(secrets.choice(alphabet) for i in range(32))
        hashed_password = auth_service.hash_password(random_password)
        
        # Ensure username is unique
        base_username = name.lower().replace(" ", "")
        username = base_username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1
            
        user = User(
            username=username,
            password_hash=hashed_password,
            email=email,
            role="user",
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Log registration
        activity_service.log_activity(
            db=db,
            user_id=user.id,
            action="register",
            ip_address=client_ip,
            user_agent=user_agent,
            status="success",
            severity="info",
            details="New user registration via Google"
        )
        logger.info(f"✅ New user registered via Google: '{username}' from {client_ip}")
    else:
        # User exists, just log login
        if not user.is_active:
            logger.warning(f"❌ Failed Google login: account inactive for '{email}' from {client_ip}")
            raise HTTPException(status_code=403, detail="Account inactive")
            
        activity_service.log_activity(
            db=db,
            user_id=user.id,
            action="login",
            ip_address=client_ip,
            user_agent=user_agent,
            status="success",
            severity="info",
            details="Login via Google"
        )
        logger.info(f"✅ Successful Google login: '{user.username}' from {client_ip}")

    # Create tokens
    access_token = auth_service.create_access_token(
        username=user.username,
        role=user.role,
        user_id=user.id
    )
    refresh_token = auth_service.create_refresh_token(
        username=user.username,
        user_id=user.id
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 604800,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email
        }
    }



# ──────────────────────────────────────────────────────────────────────────
# POST /api/auth/refresh
# ──────────────────────────────────────────────────────────────────────────

class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh_access_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_sync_db)
):
    """
    Refresh expired access token using refresh token
    
    🔄 Returns new access token AND new refresh token (rotation)
    """
    
    try:
        refresh_token = payload.refresh_token
        # Verify refresh token
        payload_data = auth_service.verify_token(refresh_token, token_type="refresh")
        user = auth_service.verify_user_from_db(db, payload_data)
        
        # Create NEW tokens (rotation)
        new_access_token = auth_service.create_access_token(
            username=user.username,
            role=user.role,
            user_id=user.id
        )
        
        new_refresh_token = auth_service.create_refresh_token(
            username=user.username,
            user_id=user.id
        )
        
        logger.info(f"✅ Token refreshed for user '{user.username}'")
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 604800
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token refresh error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")


# ──────────────────────────────────────────────────────────────────────────
# POST /api/auth/logout
# ──────────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """
    Logout current user
    
    🚨 Uses verified user from JWT token (not username parameter)
    """
    
    client_ip = auth_service.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:200]
    
    activity_service.log_activity(
        db=db,
        user_id=current_user.id,
        action="logout",
        ip_address=client_ip,
        user_agent=user_agent,
        status="success",
        severity="info"
    )
    
    logger.info(f"✅ User '{current_user.username}' logged out from {client_ip}")
    
    return {
        "message": "Successfully logged out",
        "user": current_user.username
    }


# ──────────────────────────────────────────────────────────────────────────
# POST /api/auth/register
# ──────────────────────────────────────────────────────────────────────────

@router.post("/register")
@limiter.limit("3/minute") if limiter else lambda f: f  # Rate limit: 3 registrations per minute
async def register(
    username: str,
    password: str,
    email: str,
    request: Request,
    db: Session = Depends(get_sync_db)
):
    """
    Register new user account
    
    Role defaults to 'user' (only admins can create admin accounts)
    """
    
    client_ip = auth_service.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:200]
    
    # Validate inputs
    if len(username) < 3 or len(password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Username must be 3+ chars, password 6+ chars"
        )
    
    # Check if user exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        activity_service.log_activity(
            db=db,
            user_id=None,
            action="register",
            ip_address=client_ip,
            user_agent=user_agent,
            status="failed",
            severity="warning",
            details=f"Username already exists: {username}"
        )
        
        logger.warning(f"❌ Registration failed: username '{username}' already exists")
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email exists
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        activity_service.log_activity(
            db=db,
            user_id=None,
            action="register",
            ip_address=client_ip,
            user_agent=user_agent,
            status="failed",
            severity="warning",
            details=f"Email already exists: {email}"
        )
        
        logger.warning(f"❌ Registration failed: email '{email}' already registered")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = auth_service.hash_password(password)
    new_user = User(
        username=username,
        password_hash=hashed_password,
        email=email,
        role="user",
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Log registration
    activity_service.log_activity(
        db=db,
        user_id=new_user.id,
        action="register",
        ip_address=client_ip,
        user_agent=user_agent,
        status="success",
        severity="info",
        details="New user registration"
    )
    
    logger.info(f"✅ New user registered: '{username}' from {client_ip}")
    
    return {
        "message": "User registered successfully",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role
        }
    }


# ──────────────────────────────────────────────────────────────────────────
# GET /api/auth/me (Get Current User Profile)
# ──────────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user profile"""
    
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


# ──────────────────────────────────────────────────────────────────────────
# POST /api/auth/change-password
# ──────────────────────────────────────────────────────────────────────────

@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Change user password"""
    
    client_ip = auth_service.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:200]
    
    # Verify old password
    if not auth_service.verify_password(old_password, current_user.password_hash):
        activity_service.log_activity(
            db=db,
            user_id=current_user.id,
            action="password_change",
            ip_address=client_ip,
            user_agent=user_agent,
            status="failed",
            severity="warning",
            details="Incorrect current password"
        )
        
        logger.warning(f"❌ Password change failed for '{current_user.username}': wrong password")
        raise HTTPException(status_code=401, detail="Current password incorrect")
    
    # Validate new password
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be 6+ characters")
    
    # Update password
    current_user.password_hash = auth_service.hash_password(new_password)
    db.commit()
    
    # Log successful change
    activity_service.log_activity(
        db=db,
        user_id=current_user.id,
        action="password_change",
        ip_address=client_ip,
        user_agent=user_agent,
        status="success",
        severity="info"
    )
    
    logger.info(f"✅ Password changed for user '{current_user.username}'")
    
    return {"message": "Password changed successfully"}


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/auth/forgot-password  — Step 1: request OTP
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/forgot-password")
@limiter.limit("3/minute") if limiter else lambda f: f
async def forgot_password(
    email: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_sync_db)
):
    """
    Send a 6-digit OTP to the given email address for password reset.
    Always returns 200 (to avoid email enumeration attacks).
    """
    from services.email_service import generate_otp, store_otp, send_password_reset_email

    client_ip = auth_service.get_client_ip(request)

    # Check user exists (silently fail so we don't reveal account existence)
    user = db.query(User).filter(User.email == email, User.is_active == True).first()

    if user:
        otp = generate_otp()
        store_otp(email, otp)
        # Send email in background to avoid blocking the response
        background_tasks.add_task(send_password_reset_email, email, otp)
        logger.info(f"✅ Password reset OTP task added for {email} from {client_ip}")
    else:
        logger.warning(f"⚠️  Password reset requested for unknown email: {email} from {client_ip}")

    # Always return success to prevent email enumeration
    return {"message": "If that email is registered, you will receive a reset code shortly."}


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/auth/reset-password  — Step 2: verify OTP + set new password
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/reset-password")
@limiter.limit("5/minute") if limiter else lambda f: f
async def reset_password(
    email: str,
    otp_code: str,
    new_password: str,
    request: Request,
    db: Session = Depends(get_sync_db)
):
    """
    Verify the OTP and reset user password.
    """
    from services.email_service import verify_otp

    client_ip = auth_service.get_client_ip(request)

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    # Verify OTP
    if not verify_otp(email, otp_code):
        logger.warning(f"⚠️  Invalid/expired OTP for {email} from {client_ip}")
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    # Find user
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update password
    user.password_hash = auth_service.hash_password(new_password)
    db.commit()

    activity_service.log_activity(
        db=db,
        user_id=user.id,
        action="password_reset",
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", "")[:200],
        status="success",
        severity="info",
        details="Password reset via OTP email"
    )

    logger.info(f"✅ Password reset successful for '{user.username}' from {client_ip}")
    return {"message": "Password reset successfully. You can now log in with your new password."}



# ──────────────────────────────────────────────────────────────────────────────
# POST /api/auth/forgot-username  — Step 1: request OTP for username recovery
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/forgot-username")
@limiter.limit("3/minute") if limiter else lambda f: f
async def forgot_username(
    email: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_sync_db)
):
    """
    Send a 6-digit OTP to the given email for username recovery.
    Always returns 200 to prevent email enumeration.
    """
    from services.email_service import generate_otp, store_otp_for_username, send_username_reveal_email

    client_ip = auth_service.get_client_ip(request)

    user = db.query(User).filter(User.email == email, User.is_active == True).first()

    if user:
        otp = generate_otp()
        store_otp_for_username(email, otp)
        background_tasks.add_task(send_username_reveal_email, email, otp)
        logger.info(f"✅ Username recovery OTP task added for {email} from {client_ip}")
    else:
        logger.warning(f"⚠️  Username recovery requested for unknown email: {email} from {client_ip}")

    return {"message": "If that email is registered, you will receive a verification code shortly."}


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/auth/verify-username  — Step 2: verify OTP → return username
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/verify-username")
@limiter.limit("5/minute") if limiter else lambda f: f
async def verify_username(
    email: str,
    otp_code: str,
    request: Request,
    db: Session = Depends(get_sync_db)
):
    """
    Verify OTP and return the username associated with the email.
    """
    from services.email_service import verify_otp_for_username

    client_ip = auth_service.get_client_ip(request)

    if not verify_otp_for_username(email, otp_code):
        logger.warning(f"⚠️  Invalid/expired username-recovery OTP for {email} from {client_ip}")
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    activity_service.log_activity(
        db=db,
        user_id=user.id,
        action="username_recovery",
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", "")[:200],
        status="success",
        severity="info",
        details="Username recovered via OTP email"
    )

    logger.info(f"✅ Username recovered for email '{email}' from {client_ip}")
    return {"username": user.username}


# ──────────────────────────────────────────────────────────────────────────
# User Profile Edits
# ──────────────────────────────────────────────────────────────────────────

@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile including the profile picture"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "profile_picture": current_user.profile_picture,
        "created_at": current_user.created_at
    }

class ProfilePictureRequest(BaseModel):
    profile_picture: str  # Base64 string

@router.post("/profile/picture")
@limiter.limit("10/minute") if limiter else lambda f: f
async def update_profile_picture(
    payload: ProfilePictureRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Update profile picture (Uploads to GCS)"""
    from services.storage_service import storage_service
    
    # Check max size of base64 (approx 2MB limit before decoding = 2.8MB base64)
    if len(payload.profile_picture) > 3_000_000:
        raise HTTPException(status_code=400, detail="Image size exceeds maximum allowed (2MB)")
        
    # Upload to GCS and get URL
    gcs_url = storage_service.upload_profile_picture(current_user.id, payload.profile_picture)
    
    if not gcs_url:
        raise HTTPException(status_code=500, detail="Failed to upload image")

    current_user.profile_picture = gcs_url
    db.commit()
    
    activity_service.log_activity(
        db=db, user_id=current_user.id, action="update_profile",
        ip_address=auth_service.get_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:200],
        status="success", severity="info", details="Updated profile picture (stored in GCS)"
    )
    
    return {
        "message": "Profile picture updated successfully",
        "profile_picture": gcs_url
    }


@router.post("/profile/request-otp")
@limiter.limit("3/minute") if limiter else lambda f: f
async def request_profile_otp(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Request OTP to authorize changing username or password"""
    from services.email_service import generate_otp, store_profile_otp, send_profile_update_email
    
    code = generate_otp()
    store_profile_otp(current_user.email, code)
    
    success = send_profile_update_email(current_user.email, code)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send verification email")
        
    logger.info(f"📧 Profile update OTP sent to {current_user.email}")
    return {"message": "Verification code sent to your email"}


from typing import Optional

class ProfileUpdateRequest(BaseModel):
    otp_code: Optional[str] = None
    new_username: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None

@router.post("/profile/update")
@limiter.limit("5/minute") if limiter else lambda f: f
async def update_profile_details(
    payload: ProfileUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Verify OTP (if changing password) and update username/password"""
    from services.email_service import verify_profile_otp
    
    if payload.new_password:
        if not payload.old_password:
            raise HTTPException(status_code=400, detail="Current password is required to set a new password")
        if not auth_service.verify_password(payload.old_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
            
        if not payload.otp_code:
            raise HTTPException(status_code=400, detail="OTP code is required to change password")
        if not verify_profile_otp(current_user.email, payload.otp_code):
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    changes_made = []
    
    if payload.new_username and payload.new_username != current_user.username:
        # Check if username exists
        existing = db.query(User).filter(User.username == payload.new_username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        current_user.username = payload.new_username
        changes_made.append("username")
        
    if payload.new_password:
        current_user.password_hash = auth_service.hash_password(payload.new_password)
        changes_made.append("password")
        
    if not changes_made:
        return {"message": "No changes requested"}
        
    db.commit()
    
    details_str = f"Updated profile details: {', '.join(changes_made)}"
    
    activity_service.log_activity(
        db=db, user_id=current_user.id, action="update_profile",
        ip_address=auth_service.get_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:200],
        status="success", severity="info", details=details_str
    )
    
    # We must generate new tokens if username changed
    access_token = auth_service.create_access_token(
        username=current_user.username,
        role=current_user.role,
        user_id=current_user.id
    )
    refresh_token = auth_service.create_refresh_token(
        username=current_user.username,
        user_id=current_user.id
    )
    
    return {
        "message": "Profile updated successfully",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 600,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "email": current_user.email
        }
    }
