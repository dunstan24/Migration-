"""
Admin Router
Admin-only endpoints for user management and activity monitoring
All endpoints require admin role

Access points:
  GET    /api/admin/dashboard/activity     - Combined dashboard data
  GET    /api/admin/users                  - List all users
  PATCH  /api/admin/users/{user_id}/deactivate - Deactivate user
  GET    /api/admin/users/{user_id}/activity   - Get user activity
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from db.database import get_sync_db
from db.models import User, UserActivityLog
from services.auth_service import auth_service
from services.activity_service import activity_service
import logging

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger("uvicorn.error")


# ──────────────────────────────────────────────────────────────────────────
# Dependency: Verify Admin Role
# ──────────────────────────────────────────────────────────────────────────

async def verify_admin(
    request: Request,
    db: Session = Depends(get_sync_db)
) -> User:
    """
    🚨 PROTECTED: Verify user has admin role
    Used by all admin endpoints
    """
    
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header.split(" ")[1]
    user = auth_service.get_current_user(db, token)
    
    if user.role not in ["admin", "superadmin"]:
        logger.warning(f"❌ Unauthorized admin access attempt by '{user.username}' (role: {user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access this resource"
        )
    
    logger.info(f"✅ Admin access granted to '{user.username}'")
    return user


# ──────────────────────────────────────────────────────────────────────────
# GET /api/admin/dashboard/activity - COMBINED ENDPOINT
# ──────────────────────────────────────────────────────────────────────────

@router.get("/dashboard/activity")
async def get_activity_dashboard(
    admin_user: User = Depends(verify_admin),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: int = Query(None),
    action: str = Query(None),
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_sync_db)
):
    """
    Admin Dashboard: Combined endpoint returns EVERYTHING
    
    ✅ Activities (with pagination)
    ✅ Statistics (total logins, failures, active users, critical events)
    ✅ Heatmap (hourly activity)
    
    One API call replaces three! (activities + stats + heatmap)
    """
    
    logger.info(f"Admin dashboard accessed by '{admin_user.username}' - days={days}, limit={limit}")
    
    # Get activities (uses joinedload to prevent N+1)
    activities, total = activity_service.get_activity_logs(
        db=db,
        days=days,
        user_id=user_id,
        action=action,
        limit=limit,
        offset=offset
    )
    
    # Get statistics (single optimized query)
    stats = activity_service.get_statistics(db=db, days=days)
    
    # Get heatmap (SQL aggregation)
    heatmap_data = activity_service.get_activity_heatmap(db=db, days=days)
    
    return {
        "activities": [
            {
                "id": activity["id"],
                "user_id": activity["user_id"],
                "username": activity["username"],
                "action": activity["action"],
                "severity": activity["severity"],
                "timestamp": activity["timestamp"].isoformat(),
                "ip_address": activity["ip_address"],
                "status": activity["status"],
                "details": activity["details"]
            }
            for activity in activities
        ],
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
            "page": (offset // limit) + 1
        },
        "statistics": stats,
        "heatmap": heatmap_data["heatmap"]
    }


# ──────────────────────────────────────────────────────────────────────────
# GET /api/admin/users - List All Users
# ──────────────────────────────────────────────────────────────────────────

@router.get("/users")
async def get_all_users(
    admin_user: User = Depends(verify_admin),
    db: Session = Depends(get_sync_db)
):
    """Get list of all users with activity summary"""
    
    users = db.query(User).filter(User.is_active == True).all()
    
    user_summaries = []
    for user in users:
        summary = activity_service.get_user_summary(db, user.id)
        if summary:
            user_summaries.append(summary)
    
    logger.info(f"Admin listed all users - count: {len(user_summaries)}")
    
    return {
        "total": len(user_summaries),
        "users": user_summaries
    }


# ──────────────────────────────────────────────────────────────────────────
# GET /api/admin/users/{user_id}/activity - User Activity History
# ──────────────────────────────────────────────────────────────────────────

@router.get("/users/{user_id}/activity")
async def get_user_activity(
    user_id: int,
    admin_user: User = Depends(verify_admin),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_sync_db)
):
    """Get detailed activity history for specific user"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Admin tried to access activity for non-existent user {user_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    activities, total = activity_service.get_activity_logs(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
        days=days
    )
    
    logger.info(f"Admin '{admin_user.username}' viewed activity for user '{user.username}'")
    
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email
        },
        "activities": [
            {
                "id": activity["id"],
                "action": activity["action"],
                "severity": activity["severity"],
                "timestamp": activity["timestamp"].isoformat(),
                "ip_address": activity["ip_address"],
                "status": activity["status"],
                "details": activity["details"]
            }
            for activity in activities
        ],
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total
        }
    }


# ──────────────────────────────────────────────────────────────────────────
# PATCH /api/admin/users/{user_id}/deactivate - Deactivate User
# ──────────────────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    admin_user: User = Depends(verify_admin),
    db: Session = Depends(get_sync_db)
):
    """Deactivate user account"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Admin tried to deactivate non-existent user {user_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == admin_user.id:
        logger.warning(f"Admin '{admin_user.username}' tried to deactivate themselves")
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    if user.role == "superadmin" and admin_user.role != "superadmin":
        logger.warning(f"❌ Admin '{admin_user.username}' tried to deactivate Superadmin '{user.username}'")
        raise HTTPException(status_code=403, detail="Cannot deactivate a Superadmin")
    
    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # Log the admin action
    activity_service.log_activity(
        db=db,
        user_id=admin_user.id,
        action="admin_deactivate_user",
        ip_address="internal",
        user_agent="admin-panel",
        status="success",
        severity="warning",
        details=f"Admin deactivated user {user.username}"
    )
    
    logger.warning(f"✅ Admin '{admin_user.username}' deactivated user '{user.username}'")
    
    return {
        "message": f"User '{user.username}' has been deactivated",
        "user": {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active
        }
    }


# ──────────────────────────────────────────────────────────────────────────# PATCH /api/admin/users/{user_id}/promote - Promote User to Admin
# ──────────────────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}/promote")
async def promote_user(
    user_id: int,
    admin_user: User = Depends(verify_admin),
    db: Session = Depends(get_sync_db)
):
    """Promote a regular user to admin."""

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Admin tried to promote non-existent user {user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin_user.id:
        logger.warning(f"Admin '{admin_user.username}' tried to promote themselves")
        raise HTTPException(status_code=400, detail="Cannot promote yourself")

    if user.role == "superadmin":
        raise HTTPException(status_code=400, detail="User is already a Superadmin")

    user.role = "admin"
    user.updated_at = datetime.utcnow()
    db.commit()

    activity_service.log_activity(
        db=db,
        user_id=admin_user.id,
        action="admin_promote_user",
        ip_address="internal",
        user_agent="admin-panel",
        status="success",
        severity="info",
        details=f"Admin promoted user {user.username} to admin"
    )

    logger.info(f"✅ Admin '{admin_user.username}' promoted user '{user.username}' to admin")

    return {
        "message": f"User '{user.username}' is now an admin",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email,
            "is_active": user.is_active
        }
    }


# ──────────────────────────────────────────────────────────────────────────# DELETE /api/admin/users/{user_id} - Delete User
# ──────────────────────────────────────────────────────────────────────────

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: User = Depends(verify_admin),
    db: Session = Depends(get_sync_db)
):
    """Delete user and associated activity logs."""

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Admin tried to delete non-existent user {user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin_user.id:
        logger.warning(f"Admin '{admin_user.username}' tried to delete themselves")
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    if user.role == "superadmin" and admin_user.role != "superadmin":
        logger.warning(f"❌ Admin '{admin_user.username}' tried to delete Superadmin '{user.username}'")
        raise HTTPException(status_code=403, detail="Cannot delete a Superadmin")

    # Remove related activity logs first to avoid FK constraint issues
    db.query(UserActivityLog).filter(UserActivityLog.user_id == user_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()

    activity_service.log_activity(
        db=db,
        user_id=admin_user.id,
        action="admin_delete_user",
        ip_address="internal",
        user_agent="admin-panel",
        status="success",
        severity="critical",
        details=f"Admin deleted user {user.username}"
    )

    logger.warning(f"✅ Admin '{admin_user.username}' deleted user '{user.username}'")

    return {
        "message": f"User '{user.username}' has been deleted"
    }


# ──────────────────────────────────────────────────────────────────────────
# PATCH /api/admin/users/{user_id}/reactivate - Reactivate User
# ──────────────────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: int,
    admin_user: User = Depends(verify_admin),
    db: Session = Depends(get_sync_db)
):
    """Reactivate user account"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # Log the admin action
    activity_service.log_activity(
        db=db,
        user_id=admin_user.id,
        action="admin_reactivate_user",
        ip_address="internal",
        user_agent="admin-panel",
        status="success",
        severity="info",
        details=f"Admin reactivated user {user.username}"
    )
    
    logger.info(f"✅ Admin '{admin_user.username}' reactivated user '{user.username}'")
    
    return {
        "message": f"User '{user.username}' has been reactivated",
        "user": {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active
        }
    }


# ──────────────────────────────────────────────────────────────────────────
# GET /api/admin/activity/summary - Quick Activity Summary
# ──────────────────────────────────────────────────────────────────────────

@router.get("/activity/summary")
async def get_activity_summary(
    admin_user: User = Depends(verify_admin),
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_sync_db)
):
    """Quick summary of activity metrics"""
    
    stats = activity_service.get_statistics(db=db, days=days)
    
    return {
        "summary": stats,
        "generated_at": datetime.utcnow().isoformat()
    }


# ──────────────────────────────────────────────────────────────────────────
# POST /api/admin/run-cleanup - Manual Cleanup Trigger
# ──────────────────────────────────────────────────────────────────────────

@router.post("/run-cleanup")
async def trigger_cleanup(
    admin_user: User = Depends(verify_admin),
    days_to_keep: int = Query(90, ge=1, le=365)
):
    """
    Manually trigger activity log cleanup
    Deletes logs older than specified days
    """
    
    try:
        from scripts.cleanup_activity_logs import cleanup_activity_logs_batch
        
        logger.info(f"Admin '{admin_user.username}' triggered manual cleanup (keep {days_to_keep} days)")
        
        result = cleanup_activity_logs_batch(days_to_keep=days_to_keep, batch_size=5000)
        
        return {
            "status": result["status"],
            "message": result["message"],
            "deleted_count": result["deleted_count"],
            "db_size_mb": result.get("db_size_mb", 0)
        }
    
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
