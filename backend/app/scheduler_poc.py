"""
APScheduler + SQLite + Docker Persistence Proof of Concept

This POC demonstrates:
1. APScheduler with SQLite job store for persistence
2. FastAPI lifespan integration for proper startup/shutdown
3. Job survival across Docker container restarts
4. Overlap prevention using database flags
"""

import logging
import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import ApplicationSettings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SchedulerServicePOC:
    """APScheduler service with SQLite persistence for POC testing."""

    def __init__(self):
        """Initialize scheduler with SQLite job store configuration."""

        # Configure job store for persistence across Docker restarts
        # Using separate database file from main application
        jobstores = {
            'default': SQLAlchemyJobStore(url='sqlite:///data/scheduler_jobs.db')
        }

        # Configure executors
        executors = {
            'default': AsyncIOExecutor(),
        }

        # Job defaults - critical for preventing overlapping executions
        job_defaults = {
            'coalesce': True,          # Combine multiple pending instances into one
            'max_instances': 1,        # Only allow one instance of each job at a time
            'misfire_grace_time': 300  # 5 minute grace period for late executions
        }

        # Create scheduler with persistence configuration
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'  # Always use UTC for consistency
        )

        # Add event listeners for monitoring
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)

        logger.info("SchedulerServicePOC initialized with SQLite persistence")

    async def start(self):
        """Start scheduler and restore persisted jobs."""
        try:
            self.scheduler.start()

            # Log existing jobs (recovered from SQLite)
            jobs = self.scheduler.get_jobs()
            if jobs:
                logger.info(f"Scheduler started - recovered {len(jobs)} jobs from SQLite:")
                for job in jobs:
                    logger.info(f"  - {job.id}: {job.name} (next run: {job.next_run_time})")
            else:
                logger.info("Scheduler started - no existing jobs found")

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    async def shutdown(self):
        """Gracefully shutdown scheduler."""
        try:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler shutdown completed")
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {e}")

    def _job_executed(self, event):
        """Log successful job execution."""
        logger.info(f"Job '{event.job_id}' executed successfully")

    def _job_error(self, event):
        """Log job execution errors."""
        logger.error(f"Job '{event.job_id}' failed: {event.exception}")

    def add_poc_jobs(self):
        """Add POC test jobs to demonstrate persistence."""

        # Job 1: Simple echo job every 2 minutes (for quick testing)
        self.scheduler.add_job(
            func=simple_echo_job,
            trigger='interval',
            minutes=2,
            id='poc_echo_job',
            name='POC Echo Job - Every 2 Minutes',
            replace_existing=True
        )

        # Job 2: Mock channel download job every 5 minutes (simulates real workload)
        self.scheduler.add_job(
            func=mock_channel_download_job,
            trigger='interval',
            minutes=5,
            id='poc_download_job',
            name='POC Mock Download Job - Every 5 Minutes',
            replace_existing=True
        )

        # Job 3: Restart verification job with unique timestamp (proves persistence)
        restart_verification_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.scheduler.add_job(
            func=restart_verification_job,
            trigger='interval',
            minutes=3,
            id=f'poc_restart_verification_{restart_verification_time}',
            name=f'POC Restart Verification - Created {restart_verification_time}',
            replace_existing=False  # Keep unique instances
        )

        logger.info("POC test jobs added to scheduler")


# Global scheduler instance
scheduler_service = SchedulerServicePOC()


# =============================================================================
# POC Test Job Functions
# =============================================================================

async def simple_echo_job():
    """Simple job that logs current time - proves basic scheduling works."""
    timestamp = datetime.utcnow().isoformat()
    message = f"POC Echo Job executed at {timestamp}"

    logger.info(message)

    # Write to log file for persistence verification
    try:
        with open('/app/data/poc_echo_log.txt', 'a') as f:
            f.write(f"{message}\n")
    except Exception as e:
        logger.error(f"Failed to write echo log: {e}")


async def mock_channel_download_job():
    """Mock download job that simulates real download process with overlap prevention."""
    logger.info("Starting mock channel download job")

    # Demonstrate overlap prevention using ApplicationSettings
    db = SessionLocal()
    try:
        # Check if already running (overlap prevention)
        running_flag = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == "poc_scheduler_running"
        ).first()

        if running_flag and running_flag.value == "true":
            logger.warning("Mock download job already running, skipping this execution")
            return

        # Set running flag
        if running_flag:
            running_flag.value = "true"
        else:
            running_flag = ApplicationSettings(
                key="poc_scheduler_running",
                value="true",
                description="POC flag to prevent overlapping scheduled downloads"
            )
            db.add(running_flag)
        db.commit()

        # Simulate processing multiple channels
        channels_to_process = ["Channel A", "Channel B", "Channel C"]
        total_downloaded = 0

        for channel_name in channels_to_process:
            logger.info(f"Processing mock channel: {channel_name}")

            # Simulate download time
            await asyncio.sleep(2)

            # Simulate download result
            videos_downloaded = 1  # Mock successful download
            total_downloaded += videos_downloaded

            logger.info(f"Downloaded {videos_downloaded} videos from {channel_name}")

        # Update last run timestamp
        last_run_setting = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == "poc_scheduler_last_run"
        ).first()

        current_time = datetime.utcnow().isoformat()
        if last_run_setting:
            last_run_setting.value = current_time
        else:
            last_run_setting = ApplicationSettings(
                key="poc_scheduler_last_run",
                value=current_time,
                description="POC timestamp of last successful scheduled download"
            )
            db.add(last_run_setting)

        db.commit()

        logger.info(f"Mock download job completed. Total videos downloaded: {total_downloaded}")

        # Write to log file for persistence verification
        try:
            with open('/app/data/poc_download_log.txt', 'a') as f:
                f.write(f"{current_time}: Completed mock download - {total_downloaded} videos\n")
        except Exception as e:
            logger.error(f"Failed to write download log: {e}")

    except Exception as e:
        logger.error(f"Error in mock download job: {e}")
    finally:
        # Always clear running flag
        if running_flag:
            running_flag.value = "false"
            db.commit()
        db.close()


async def restart_verification_job():
    """Job that proves scheduler survives container restarts."""
    timestamp = datetime.utcnow().isoformat()
    message = f"POC Restart Verification Job executed at {timestamp}"

    logger.info(message)

    # Write to persistent log file
    try:
        with open('/app/data/poc_restart_verification.txt', 'a') as f:
            f.write(f"{message}\n")
    except Exception as e:
        logger.error(f"Failed to write restart verification log: {e}")


# =============================================================================
# FastAPI Integration with Lifespan Context Manager
# =============================================================================

@asynccontextmanager
async def scheduler_lifespan(app: FastAPI):
    """FastAPI lifespan context manager for scheduler startup/shutdown."""

    # Startup
    logger.info("Starting APScheduler POC with FastAPI lifespan")

    try:
        # Start the scheduler
        await scheduler_service.start()

        # Add POC test jobs (only if not already present from previous run)
        existing_jobs = scheduler_service.scheduler.get_jobs()
        if len(existing_jobs) == 0:
            scheduler_service.add_poc_jobs()
            logger.info("Added new POC test jobs")
        else:
            logger.info(f"Using existing jobs from SQLite: {[job.id for job in existing_jobs]}")

        logger.info("APScheduler POC startup completed successfully")

    except Exception as e:
        logger.error(f"APScheduler POC startup failed: {e}")
        raise

    # Yield control to FastAPI
    yield

    # Shutdown
    logger.info("Shutting down APScheduler POC")
    await scheduler_service.shutdown()


# =============================================================================
# POC Status and Monitoring Functions
# =============================================================================

def get_scheduler_status() -> dict:
    """Get current scheduler status for monitoring."""
    try:
        jobs = scheduler_service.scheduler.get_jobs()

        status = {
            "scheduler_running": scheduler_service.scheduler.running,
            "total_jobs": len(jobs),
            "jobs": []
        }

        for job in jobs:
            job_info = {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            status["jobs"].append(job_info)

        return status

    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return {"error": str(e)}


def get_poc_logs() -> dict:
    """Read POC log files to show persistence across restarts."""
    logs = {}

    log_files = {
        "echo_log": "/app/data/poc_echo_log.txt",
        "download_log": "/app/data/poc_download_log.txt",
        "restart_verification": "/app/data/poc_restart_verification.txt"
    }

    for log_name, file_path in log_files.items():
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
                logs[log_name] = {
                    "total_lines": len(lines),
                    "latest_entries": lines[-5:] if lines else []  # Last 5 entries
                }
        except FileNotFoundError:
            logs[log_name] = {"status": "File not yet created"}
        except Exception as e:
            logs[log_name] = {"error": str(e)}

    return logs


# =============================================================================
# POC FastAPI Application
# =============================================================================

def create_poc_app() -> FastAPI:
    """Create POC FastAPI application with scheduler integration."""

    app = FastAPI(
        title="APScheduler SQLite Persistence POC",
        description="Proof of concept for APScheduler with SQLite job store and Docker persistence",
        version="1.0.0",
        lifespan=scheduler_lifespan
    )

    @app.get("/poc/scheduler/status")
    async def poc_scheduler_status():
        """Get current scheduler status and job information."""
        return get_scheduler_status()

    @app.get("/poc/scheduler/logs")
    async def poc_scheduler_logs():
        """Get POC log files to verify persistence."""
        return get_poc_logs()

    @app.post("/poc/scheduler/add-test-job")
    async def poc_add_test_job():
        """Add a one-time test job to verify scheduler is working."""
        try:
            # Add a job that runs in 30 seconds
            run_time = datetime.utcnow() + timedelta(seconds=30)

            scheduler_service.scheduler.add_job(
                func=simple_echo_job,
                trigger='date',
                run_date=run_time,
                id=f'poc_manual_test_{datetime.now().strftime("%H%M%S")}',
                name=f'POC Manual Test Job - {run_time.strftime("%H:%M:%S")}',
                replace_existing=False
            )

            return {
                "success": True,
                "message": f"Test job scheduled to run at {run_time.isoformat()}",
                "run_time": run_time.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to add test job: {e}")
            return {"success": False, "error": str(e)}

    return app


if __name__ == "__main__":
    # This allows running the POC standalone for testing
    import uvicorn

    poc_app = create_poc_app()
    uvicorn.run(poc_app, host="0.0.0.0", port=8001, log_level="info")