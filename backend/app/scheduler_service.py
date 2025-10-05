"""Production scheduler service with SQLite persistence and Docker integration.

This module provides the core scheduler infrastructure using APScheduler with
SQLite job storage for persistence across Docker container restarts.

Key Features:
- SQLite job persistence (survives container restarts)
- Async execution with FastAPI integration
- Event-based job monitoring
- Automatic schedule loading from database
- Stale lock recovery on startup
- Graceful shutdown with job completion

Architecture:
- Uses APScheduler's AsyncIOScheduler for async job execution
- Stores jobs in SQLite database (data/scheduler_jobs.db)
- Loads cron schedule from ApplicationSettings on startup
- Integrates with overlap prevention mechanism
- Provides status monitoring for API endpoints

Usage:
    from app.scheduler_service import scheduler_service

    # In FastAPI lifespan
    async def lifespan(app: FastAPI):
        await scheduler_service.start()
        yield
        await scheduler_service.shutdown()
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ApplicationSettings
from app.overlap_prevention import clear_stale_locks

logger = logging.getLogger(__name__)


class SchedulerService:
    """Production scheduler service with SQLite persistence and Docker integration.

    This service manages all scheduled jobs for the application, including:
    - Automatic video downloads based on cron schedules
    - Job persistence across container restarts
    - Overlap prevention for concurrent executions
    - Event-based monitoring and logging

    The scheduler is initialized once at application startup and runs continuously
    until shutdown. Jobs are stored in SQLite and automatically recovered after
    container restarts.
    """

    def __init__(self):
        """Initialize scheduler with production-ready configuration.

        Configuration:
        - Job Store: SQLite database at data/scheduler_jobs.db
        - Executor: AsyncIO for async job execution
        - Timezone: UTC for consistency
        - Job Defaults: Prevent overlaps, 5-minute grace period for misfires
        """

        # SQLite job store configuration for Docker persistence
        jobstores = {
            'default': SQLAlchemyJobStore(
                url='sqlite:///data/scheduler_jobs.db',
                tablename='apscheduler_jobs'
            )
        }

        # Async executor configuration
        executors = {
            'default': AsyncIOExecutor(),
        }

        # Production job defaults for reliability
        job_defaults = {
            'coalesce': True,          # Combine multiple pending instances into one
            'max_instances': 1,        # Prevent overlapping executions
            'misfire_grace_time': 300, # 5-minute grace period for delayed starts
            'replace_existing': True   # Update existing jobs on restart
        }

        # Create scheduler with UTC timezone for consistency
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        # Add event listeners for monitoring
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)

        logger.info("SchedulerService initialized with SQLite persistence")

    async def start(self):
        """Start scheduler and restore persisted jobs.

        Startup sequence:
        1. Clear any stale locks from previous crashes
        2. Start the APScheduler
        3. Load cron schedule from database
        4. Log recovered jobs for monitoring

        Raises:
            Exception: If scheduler fails to start
        """
        try:
            # Clear stale locks from previous runs (crash recovery)
            db = SessionLocal()
            try:
                cleared_locks = clear_stale_locks(db, max_age_hours=2)
                if cleared_locks > 0:
                    logger.info(f"Startup: Cleared {cleared_locks} stale lock(s)")
            finally:
                db.close()

            # Start the scheduler
            self.scheduler.start()

            # Load and configure cron schedule from database
            await self._load_cron_schedule()

            # Log recovered jobs
            jobs = self.scheduler.get_jobs()
            if jobs:
                logger.info(f"Scheduler started - recovered {len(jobs)} jobs:")
                for job in jobs:
                    logger.info(f"  - {job.id}: {job.name}")
                    if job.next_run_time:
                        logger.info(f"    Next run: {job.next_run_time}")
            else:
                logger.info("Scheduler started - no existing jobs found")

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    async def shutdown(self):
        """Gracefully shutdown scheduler with job completion.

        Waits for currently running jobs to complete before shutting down.
        This ensures no jobs are interrupted during application shutdown.
        """
        try:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler shutdown completed")
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {e}")

    async def _load_cron_schedule(self):
        """Load cron schedule from database and configure main download job.

        Checks ApplicationSettings for:
        - cron_schedule: The cron expression to use
        - scheduler_enabled: Whether scheduler should be active

        Only creates the download job if both settings are present and enabled.
        """
        db = SessionLocal()
        try:
            cron_setting = db.query(ApplicationSettings).filter(
                ApplicationSettings.key == "cron_schedule"
            ).first()

            enabled_setting = db.query(ApplicationSettings).filter(
                ApplicationSettings.key == "scheduler_enabled"
            ).first()

            if (cron_setting and cron_setting.value and
                enabled_setting and enabled_setting.value == "true"):

                # Add/update the main download job
                self.update_download_schedule(cron_setting.value)
                logger.info(f"Loaded cron schedule: {cron_setting.value}")
            else:
                logger.info("No active cron schedule found in database")

        except Exception as e:
            logger.error(f"Failed to load cron schedule: {e}")
        finally:
            db.close()

    def update_download_schedule(self, cron_expression: str):
        """Update or create the main download job with new cron schedule.

        Args:
            cron_expression: 5-field cron expression (e.g., "0 */6 * * *")

        Raises:
            ValueError: If cron expression is invalid

        Note:
            This method is called both during startup (from _load_cron_schedule)
            and when users update the schedule via API.
        """
        try:
            # Import here to avoid circular dependency
            from app.scheduled_download_job import scheduled_download_job

            # Parse cron expression into trigger
            trigger = CronTrigger.from_crontab(cron_expression, timezone='UTC')

            # Add/update the download job
            self.scheduler.add_job(
                func=scheduled_download_job,
                trigger=trigger,
                id='main_download_job',
                name='Scheduled Channel Downloads',
                replace_existing=True
            )

            logger.info(f"Updated download schedule: {cron_expression}")

        except ImportError:
            # scheduled_download_job not yet implemented, skip for now
            logger.warning("scheduled_download_job not yet implemented, skipping job creation")
        except Exception as e:
            logger.error(f"Failed to update download schedule: {e}")
            raise

    def get_schedule_status(self) -> Dict:
        """Get current schedule status for monitoring.

        Returns:
            Dictionary containing:
            - scheduler_running: bool - Is a job currently executing (not just if APScheduler is active)
            - total_jobs: int - Number of scheduled jobs
            - download_job_active: bool - Is main download job scheduled
            - next_run_time: str or None - ISO timestamp of next run
            - job_details: List[Dict] - Details of all scheduled jobs

        Example:
            >>> status = scheduler_service.get_schedule_status()
            >>> print(status['next_run_time'])
            "2025-10-02T00:00:00+00:00"
        """
        try:
            jobs = self.scheduler.get_jobs()
            download_job = self.scheduler.get_job('main_download_job')

            # Check if a job is ACTUALLY running by looking at the database flag
            # (not just whether APScheduler service is started)
            db = SessionLocal()
            try:
                running_flag = db.query(ApplicationSettings).filter(
                    ApplicationSettings.key == "scheduled_downloads_running"
                ).first()
                # Ensure boolean conversion: None → False, missing setting → False
                job_currently_executing = bool(running_flag and running_flag.value == "true")
            finally:
                db.close()

            return {
                "scheduler_running": job_currently_executing,  # Fixed: Now checks actual job execution state
                "total_jobs": len(jobs),
                "download_job_active": download_job is not None,
                "next_run_time": download_job.next_run_time.isoformat() if download_job and download_job.next_run_time else None,
                "job_details": [
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                    }
                    for job in jobs
                ]
            }
        except Exception as e:
            logger.error(f"Error getting schedule status: {e}")
            return {"error": str(e)}

    def _job_executed(self, event):
        """Log successful job execution.

        Args:
            event: APScheduler job execution event
        """
        logger.info(f"Job '{event.job_id}' executed successfully")

    def _job_error(self, event):
        """Log job execution errors.

        Args:
            event: APScheduler job error event
        """
        logger.error(f"Job '{event.job_id}' failed: {event.exception}")


# Global scheduler instance
# This single instance is used throughout the application
scheduler_service = SchedulerService()
