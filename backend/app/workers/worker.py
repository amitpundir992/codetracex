#!/usr/bin/env python
"""
Worker entry point for CodeTraceX Phase 14+15.

Phase 15: Production Hardening
- Structured logging
- Graceful shutdown
- Error handling

Usage:
    python -m app.workers.worker

This script starts an RQ worker that processes jobs from the Redis queue.
"""
import sys
import signal
import logging
from typing import Optional
from rq import Worker
from rq.job import Job

from app.workers.redis_connection import get_redis_connection
from app.core.config import get_settings
from app.core.config_validation import validate_configuration, ConfigurationError
from app.utils.logging_config import configure_logging

# Get settings
settings = get_settings()

# Configure logging
log_level = "DEBUG" if settings.APP_ENV == "development" else "INFO"
configure_logging(level=log_level, use_json=False)  # Workers use text format

logger = logging.getLogger(__name__)

# Global worker reference for graceful shutdown
worker_instance: Optional[Worker] = None


def signal_handler(signum, frame):
    """
    Handle shutdown signals gracefully.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name}, shutting down gracefully...")
    
    if worker_instance:
        worker_instance.request_stop()
    else:
        sys.exit(0)


def exception_handler(job: Job, exc_type, exc_value, traceback):
    """
    Handle job exceptions.
    
    This prevents one failed job from killing the worker.
    
    Args:
        job: RQ job that failed
        exc_type: Exception type
        exc_value: Exception instance
        traceback: Exception traceback
    """
    logger.error(
        f"Job {job.id} failed with {exc_type.__name__}: {exc_value}",
        exc_info=(exc_type, exc_value, traceback)
    )
    
    # Job failure is already recorded by RQ, we just log it
    return False  # Return False to mark job as failed


def register_scheduled_tasks(conn):
    """
    Register scheduled tasks with RQ scheduler.
    
    Phase 25: Automated recovery
    
    Scheduled tasks:
    - Stale analysis recovery (every 30 minutes)
    
    Note: RQ's built-in scheduler runs jobs using the 'scheduled_time' parameter.
    For Phase 25, we use a simpler approach: a dedicated task that can be 
    manually triggered or run via cron/systemd timer.
    
    Future enhancement: Use RQ scheduler or APScheduler for fully automated execution.
    
    Args:
        conn: Redis connection
    """
    # Phase 25 Note: RQ's scheduler is designed for one-time delayed jobs
    # Recurring tasks are better handled by:
    # 1. External cron/systemd timer calling the task
    # 2. APScheduler library for in-process scheduling
    # 3. Kubernetes CronJob for cloud deployments
    #
    # For now, we log that scheduled tasks are available but not auto-registered
    logger.info(
        "Phase 25 recovery tasks available for manual/cron execution: "
        "recover_stale_analyses_task"
    )
    logger.info(
        "To enable automated recovery, configure a cron job or systemd timer: "
        "rq enqueue app.workers.scheduled_tasks.recover_stale_analyses_task"
    )


def main():
    """
    Start the RQ worker.
    
    The worker listens to the 'analysis' queue and processes jobs.
    
    Phase 25: Includes automated scheduled tasks for recovery.
    """
    global worker_instance
    
    logger.info("=" * 60)
    logger.info("CodeTraceX Background Worker")
    logger.info("=" * 60)
    
    # Validate configuration
    try:
        validate_configuration()
    except ConfigurationError as e:
        logger.critical(f"Configuration validation failed: {e}")
        sys.exit(1)
    
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Queue: analysis")
    logger.info(f"Job timeout: {settings.JOB_TIMEOUT}s")
    logger.info(f"Worker name: codetracex-worker")
    logger.info("=" * 60)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Get Redis connection
        conn = get_redis_connection()
        
        # Phase 25: Register scheduled tasks
        register_scheduled_tasks(conn)
        
        # Create worker
        worker_instance = Worker(
            queues=['analysis'],
            connection=conn,
            name='codetracex-worker'
        )
        
        # Set exception handler to prevent worker death on job failure
        worker_instance.push_exc_handler(exception_handler)
        
        # Start worker
        logger.info("Worker started. Waiting for jobs...")
        logger.info("Press Ctrl+C to stop gracefully")
        
        # Work with scheduler support (Phase 25: required for scheduled tasks)
        worker_instance.work(with_scheduler=True)
        
        logger.info("Worker stopped normally")
        
    except KeyboardInterrupt:
        logger.info("\nWorker stopped by user")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        # Cleanup resources
        logger.info("Worker cleanup starting...")
        
        # Close database connections
        from app.db.session import close_db_connections
        try:
            close_db_connections()
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
        
        # Close Redis connections
        from app.workers.redis_connection import close_redis_connections
        try:
            close_redis_connections()
        except Exception as e:
            logger.error(f"Error closing Redis connections: {e}")
        
        logger.info("Worker cleanup complete")


if __name__ == "__main__":
    main()
