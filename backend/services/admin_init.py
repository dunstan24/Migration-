import logging
from sqlalchemy.orm import Session
from db.database import SessionLocal
from db.models import User
from services.auth_service import auth_service
import os

logger = logging.getLogger("uvicorn.error")

def ensure_superadmin():
    """
    Check if a superadmin exists in the database.
    If not, create a default one based on environment variables or defaults.
    """
    db = SessionLocal()
    try:
        # Check if any superadmin exists
        superadmin = db.query(User).filter(User.role == "superadmin").first()
        
        if not superadmin:
            logger.info("🚀 No superadmin found. Creating default superadmin...")
            
            # Default credentials
            admin_username = os.getenv("ADMIN_USERNAME", "superadmin")
            admin_email = os.getenv("ADMIN_EMAIL", "admin@migrationintelligence.com")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123456")
            
            # Hash password using global auth_service instance
            hashed_pwd = auth_service.hash_password(admin_password)
            
            new_admin = User(
                username=admin_username,
                email=admin_email,
                password_hash=hashed_pwd,
                role="superadmin",
                is_active=True
            )
            
            db.add(new_admin)
            db.commit()
            logger.info(f"✅ Default superadmin created: {admin_username} ({admin_email})")
            logger.info("⚠️  PLEASE CHANGE THE DEFAULT PASSWORD IMMEDIATELY!")
        else:
            logger.info("✅ Superadmin account verified.")
            
    except Exception as e:
        logger.error(f"❌ Error ensuring superadmin: {e}")
        db.rollback()
    finally:
        db.close()
