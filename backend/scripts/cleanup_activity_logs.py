"""
Batch cleanup for activity logs - prevents database lock on large deletes.

CRITICAL for systems with 11M+ rows:
- Deletes in chunks of 5000 rows
- Commits after each batch (releases locks)
- Prevents CPU spike and API freezes
- Logs progress for monitoring
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import delete, func
from sqlalchemy.orm import Session
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from db.database import engine
from db.models import UserActivityLog
import logging

logger = logging.getLogger(__name__)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def cleanup_activity_logs_batch(days_to_keep: int = 90, batch_size: int = 5000) -> dict:
    """
    Delete activity logs older than N days in BATCHES to prevent DB lock.
    
    🚨 CRITICAL: Uses batching to avoid:
    - Database locks
    - CPU spikes  
    - API freezes
    - Long transaction times
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    total_deleted = 0
    batch_count = 0
    
    logger.info(f"🗑️  Starting cleanup: delete logs older than {cutoff_date.isoformat()}")
    logger.info(f"📦 Batch size: {batch_size} rows")
    
    with Session(engine) as db:
        try:
            while True:
                batch_count += 1
                
                # Get count before this batch
                count = db.query(UserActivityLog).filter(
                    UserActivityLog.timestamp < cutoff_date
                ).count()
                
                if count == 0:
                    logger.info(f"✓ Cleanup complete! Deleted {total_deleted} total rows")
                    break
                
                # Delete ONE batch
                stmt = delete(UserActivityLog).where(
                    UserActivityLog.timestamp < cutoff_date
                ).limit(batch_size)
                
                result = db.execute(stmt)
                db.commit()  # 🚨 CRITICAL: commit after each batch to release locks
                
                rows_deleted = result.rowcount
                total_deleted += rows_deleted
                
                logger.info(
                    f"  Batch {batch_count}: Deleted {rows_deleted} rows "
                    f"(Total: {total_deleted}) - {count - rows_deleted} remaining"
                )
                
                # Prevent blocking after each batch - gives API time to respond
                if rows_deleted < batch_size:
                    break
        
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {str(e)}")
            db.rollback()
            return {
                "status": "error",
                "message": f"Cleanup failed: {str(e)}",
                "deleted_count": total_deleted,
                "cutoff_date": cutoff_date.isoformat()
            }
    
    # Get database size
    db_path = backend_path / "data" / "processed" / "warehouse.db"
    db_size_mb = 0
    if db_path.exists():
        db_size_mb = db_path.stat().st_size / (1024 * 1024)
    
    return {
        "status": "success",
        "message": f"Successfully deleted {total_deleted} activity logs older than {days_to_keep} days",
        "deleted_count": total_deleted,
        "batch_count": batch_count,
        "cutoff_date": cutoff_date.isoformat(),
        "db_size_mb": round(db_size_mb, 2)
    }


if __name__ == "__main__":
    # Manual testing
    result = cleanup_activity_logs_batch(days_to_keep=90, batch_size=5000)
    print("\n" + "="*60)
    print(f"Cleanup Result: {result['status'].upper()}")
    print("="*60)
    for key, value in result.items():
        print(f"  {key}: {value}")
    print("="*60)
