"""
Timing utilities for performance observability.

Phase 24: Repository Intelligence Quality & Analysis Reliability

This module provides context managers and utilities for measuring
execution time of analysis pipeline stages.
"""
import time
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class StageTiming:
    """
    Records timing information for analysis pipeline stages.
    
    Phase 24: Observability
    """
    
    def __init__(self):
        """Initialize empty timing data."""
        self.stages = {}
        self.total_duration = 0.0
    
    def record_stage(self, stage_name: str, duration_seconds: float):
        """
        Record duration for a pipeline stage.
        
        Args:
            stage_name: Name of the stage
            duration_seconds: Duration in seconds
        """
        self.stages[stage_name] = duration_seconds
        logger.info(f"Stage '{stage_name}' completed in {duration_seconds:.2f}s")
    
    def set_total_duration(self, duration_seconds: float):
        """
        Set total pipeline duration.
        
        Args:
            duration_seconds: Total duration in seconds
        """
        self.total_duration = duration_seconds
    
    def get_summary(self) -> dict:
        """
        Get timing summary.
        
        Returns:
            Dictionary with stage timings and total duration
        """
        return {
            'total_duration_seconds': round(self.total_duration, 2),
            'stages': {k: round(v, 2) for k, v in self.stages.items()}
        }
    
    def log_summary(self):
        """Log timing summary."""
        summary = self.get_summary()
        logger.info(f"Analysis timing summary: total={summary['total_duration_seconds']}s")
        for stage, duration in summary['stages'].items():
            logger.info(f"  - {stage}: {duration}s")


@contextmanager
def timed_stage(stage_name: str, timing: Optional[StageTiming] = None):
    """
    Context manager for timing a stage.
    
    Usage:
        with timed_stage("Download repository", timing):
            download_repository(...)
    
    Args:
        stage_name: Name of the stage being timed
        timing: Optional StageTiming instance to record to
    
    Yields:
        None
    """
    start_time = time.time()
    
    try:
        yield
    finally:
        duration = time.time() - start_time
        
        if timing:
            timing.record_stage(stage_name, duration)
        else:
            logger.info(f"Stage '{stage_name}' completed in {duration:.2f}s")
