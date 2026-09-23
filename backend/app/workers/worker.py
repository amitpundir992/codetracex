#!/usr/bin/env python
"""
Worker entry point for CodeTraceX Phase 14.

Usage:
    python -m app.workers.worker

This script starts an RQ worker that processes jobs from the Redis queue.
"""
import sys
import logging
from rq import Worker
from app.workers.redis_connection import get_redis_connection
from app.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """
    Start the RQ worker.
    
    The worker listens to the 'analysis' queue and processes jobs.
    """
    settings = get_settings()
    
    logger.info("=" * 60)
    logger.info("CodeTraceX Background Worker")
    logger.info("=" * 60)
    logger.info(f"Redis URL: {settings.REDIS_URL}")
    logger.info(f"Queue: analysis")
    logger.info(f"Job timeout: {settings.JOB_TIMEOUT}s")
    logger.info("=" * 60)
    
    # Get Redis connection
    conn = get_redis_connection()
    
    # Create worker
    worker = Worker(
        queues=['analysis'],
        connection=conn,
        name='codetracex-worker'
    )
    
    # Start worker
    logger.info("Worker started. Waiting for jobs...")
    logger.info("Press Ctrl+C to stop")
    
    try:
        worker.work(with_scheduler=True)
    except KeyboardInterrupt:
        logger.info("\nWorker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
