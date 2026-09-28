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


def main():
    """
    Start the RQ worker.
    
    The worker listens to the 'analysis' queue and processes jobs.
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
        
        # Work with scheduler support
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
