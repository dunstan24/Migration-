"""
Background scheduler for Activity Log Cleanup

🚨 IMPORTANT: Only runs on ONE instance (guard prevents multiple workers)
"""

import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from scripts.cleanup_activity_logs import cleanup_activity_logs_batch

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None


def start_scheduler():
    """
    Start background scheduler for cleanup jobs.
    
    🚨 Only runs if RUN_SCHEDULER=true in .env
    Prevents duplicate runs on multi-worker deployments
    """
    
    global _scheduler
    
    # Guard: only run if explicitly enabled
    run_scheduler = os.getenv("RUN_SCHEDULER", "false").lower() == "true"
    
    if not run_scheduler:
        logger.info("⏭️  Scheduler disabled (RUN_SCHEDULER not set to 'true')")
        return None
    
    try:
        _scheduler = BackgroundScheduler()
        
        # Add cleanup job: runs daily at 2 AM
        _scheduler.add_job(
            cleanup_activity_logs_batch,
            'cron',
            hour=2,
            minute=0,
            kwargs={'days_to_keep': 90, 'batch_size': 5000},
            id='activity_log_cleanup',
            name='Clean activity logs older than 90 days',
            misfire_grace_time=600  # Allow 10 min grace for missed execution
        )
        
        _scheduler.start()
        logger.info("✅ Activity log cleanup scheduler started (daily at 2:00 AM)")
        logger.info("📋 Jobs scheduled:")
        for job in _scheduler.get_jobs():
            logger.info(f"   - {job.name} ({job.trigger})")
        
        return _scheduler
    
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {str(e)}")
        return None


def stop_scheduler():
    """Gracefully stop scheduler"""
    
    global _scheduler
    
    if not _scheduler:
        return
    
    try:
        _scheduler.shutdown()
        logger.info("✅ Activity log cleanup scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Failed to stop scheduler: {str(e)}")


def get_scheduler():
    """Get current scheduler instance"""
    return _scheduler
