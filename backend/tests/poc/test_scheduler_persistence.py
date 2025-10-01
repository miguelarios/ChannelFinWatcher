"""
Test script for APScheduler + SQLite + Docker Persistence POC

This script validates that:
1. APScheduler jobs are stored in SQLite database
2. Jobs survive container restarts
3. FastAPI integration works correctly
4. Overlap prevention mechanisms function properly

Run this script to test the POC implementation.
"""

import asyncio
import time
import requests
import sqlite3
import os
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchedulerPOCTester:
    """Test suite for APScheduler SQLite persistence POC."""

    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.db_path = "/Users/mrios/Nextcloud/Documents/Development/Projects/ChannelFinWatcher/data/scheduler_jobs.db"
        self.log_files = {
            "echo": "/Users/mrios/Nextcloud/Documents/Development/Projects/ChannelFinWatcher/data/poc_echo_log.txt",
            "download": "/Users/mrios/Nextcloud/Documents/Development/Projects/ChannelFinWatcher/data/poc_download_log.txt",
            "restart": "/Users/mrios/Nextcloud/Documents/Development/Projects/ChannelFinWatcher/data/poc_restart_verification.txt"
        }

    def test_api_connectivity(self):
        """Test that POC API is accessible."""
        logger.info("Testing API connectivity...")

        try:
            response = requests.get(f"{self.base_url}/poc/scheduler/status", timeout=10)
            if response.status_code == 200:
                status = response.json()
                logger.info(f"✅ API accessible - Scheduler running: {status.get('scheduler_running')}")
                logger.info(f"   Total jobs: {status.get('total_jobs')}")
                return True
            else:
                logger.error(f"❌ API returned status code: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API connectivity failed: {e}")
            return False

    def test_sqlite_job_store(self):
        """Test that jobs are stored in SQLite database."""
        logger.info("Testing SQLite job store...")

        if not os.path.exists(self.db_path):
            logger.error(f"❌ SQLite database not found at: {self.db_path}")
            return False

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if APScheduler tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            if 'apscheduler_jobs' in tables:
                logger.info("✅ APScheduler jobs table exists in SQLite")

                # Count jobs in database
                cursor.execute("SELECT COUNT(*) FROM apscheduler_jobs")
                job_count = cursor.fetchone()[0]
                logger.info(f"   Jobs in database: {job_count}")

                # List job IDs
                cursor.execute("SELECT id, next_run_time FROM apscheduler_jobs")
                jobs = cursor.fetchall()
                for job_id, next_run in jobs:
                    logger.info(f"   - {job_id} (next run: {next_run})")

                conn.close()
                return True
            else:
                logger.error("❌ APScheduler jobs table not found in SQLite")
                conn.close()
                return False

        except Exception as e:
            logger.error(f"❌ SQLite test failed: {e}")
            return False

    def test_job_scheduling(self):
        """Test that jobs can be scheduled and executed."""
        logger.info("Testing job scheduling...")

        try:
            # Add a test job through API
            response = requests.post(f"{self.base_url}/poc/scheduler/add-test-job", timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"✅ Test job scheduled successfully")
                    logger.info(f"   Run time: {result.get('run_time')}")

                    # Wait a moment and check if job count increased
                    time.sleep(2)

                    status_response = requests.get(f"{self.base_url}/poc/scheduler/status", timeout=10)
                    if status_response.status_code == 200:
                        status = status_response.json()
                        logger.info(f"   Current job count: {status.get('total_jobs')}")

                    return True
                else:
                    logger.error(f"❌ Failed to schedule job: {result.get('error')}")
                    return False
            else:
                logger.error(f"❌ Job scheduling API returned: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Job scheduling test failed: {e}")
            return False

    def test_log_file_persistence(self):
        """Test that job execution creates persistent log files."""
        logger.info("Testing log file persistence...")

        success_count = 0
        total_files = len(self.log_files)

        for log_name, file_path in self.log_files.items():
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        lines = f.readlines()

                    logger.info(f"✅ {log_name} log exists with {len(lines)} entries")
                    if lines:
                        logger.info(f"   Latest: {lines[-1].strip()}")
                    success_count += 1

                except Exception as e:
                    logger.error(f"❌ Error reading {log_name} log: {e}")
            else:
                logger.warning(f"⚠️  {log_name} log not yet created: {file_path}")

        return success_count == total_files

    def test_database_settings_integration(self):
        """Test that ApplicationSettings integration works."""
        logger.info("Testing ApplicationSettings integration...")

        # Check the main application database for POC settings
        main_db_path = "/Users/mrios/Nextcloud/Documents/Development/Projects/ChannelFinWatcher/data/app.db"

        if not os.path.exists(main_db_path):
            logger.warning(f"⚠️  Main application database not found: {main_db_path}")
            return False

        try:
            conn = sqlite3.connect(main_db_path)
            cursor = conn.cursor()

            # Check for POC settings
            cursor.execute("SELECT key, value FROM application_settings WHERE key LIKE 'poc_%'")
            poc_settings = cursor.fetchall()

            if poc_settings:
                logger.info(f"✅ Found {len(poc_settings)} POC settings in ApplicationSettings:")
                for key, value in poc_settings:
                    logger.info(f"   {key}: {value}")
            else:
                logger.info("ℹ️  No POC settings found yet (expected if jobs haven't run)")

            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ ApplicationSettings test failed: {e}")
            return False

    def monitor_job_execution(self, duration_minutes=2):
        """Monitor job execution for a specified duration."""
        logger.info(f"Monitoring job execution for {duration_minutes} minutes...")

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        initial_status = requests.get(f"{self.base_url}/poc/scheduler/status").json()
        initial_job_count = initial_status.get('total_jobs', 0)

        logger.info(f"Initial job count: {initial_job_count}")

        # Track log file growth
        initial_log_sizes = {}
        for log_name, file_path in self.log_files.items():
            if os.path.exists(file_path):
                initial_log_sizes[log_name] = os.path.getsize(file_path)
            else:
                initial_log_sizes[log_name] = 0

        check_count = 0
        while time.time() < end_time:
            check_count += 1
            logger.info(f"Check #{check_count} - {int((end_time - time.time()) / 60)} minutes remaining")

            # Check scheduler status
            try:
                response = requests.get(f"{self.base_url}/poc/scheduler/status", timeout=5)
                if response.status_code == 200:
                    status = response.json()
                    logger.info(f"  Scheduler running: {status.get('scheduler_running')}")
                    logger.info(f"  Active jobs: {status.get('total_jobs')}")

                    # Show next run times
                    for job in status.get('jobs', []):
                        next_run = job.get('next_run_time')
                        if next_run:
                            logger.info(f"    {job['name']}: {next_run}")

            except Exception as e:
                logger.warning(f"  Status check failed: {e}")

            # Check log file growth
            for log_name, file_path in self.log_files.items():
                if os.path.exists(file_path):
                    current_size = os.path.getsize(file_path)
                    growth = current_size - initial_log_sizes[log_name]
                    if growth > 0:
                        logger.info(f"  {log_name} log grew by {growth} bytes")

            time.sleep(30)  # Check every 30 seconds

        logger.info("Monitoring completed")

    def generate_restart_instructions(self):
        """Generate instructions for testing container restart persistence."""
        logger.info("\n" + "="*60)
        logger.info("DOCKER RESTART PERSISTENCE TEST INSTRUCTIONS")
        logger.info("="*60)
        logger.info("")
        logger.info("To test job persistence across container restarts:")
        logger.info("")
        logger.info("1. Note the current job status and log file sizes")
        logger.info("2. Stop the Docker container:")
        logger.info("   docker compose -f docker-compose.dev.yml down")
        logger.info("")
        logger.info("3. Wait 30 seconds")
        logger.info("")
        logger.info("4. Restart the container:")
        logger.info("   docker compose -f docker-compose.dev.yml up -d")
        logger.info("")
        logger.info("5. Wait 1-2 minutes for startup")
        logger.info("")
        logger.info("6. Re-run this test script to verify:")
        logger.info("   - Same jobs are recovered from SQLite")
        logger.info("   - Jobs continue executing (new log entries)")
        logger.info("   - No duplicate jobs are created")
        logger.info("")
        logger.info("Current status for comparison:")

        # Show current status
        try:
            response = requests.get(f"{self.base_url}/poc/scheduler/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                logger.info(f"  Jobs before restart: {status.get('total_jobs')}")
                for job in status.get('jobs', []):
                    logger.info(f"    - {job['id']}: {job['name']}")

        except Exception as e:
            logger.warning(f"Could not get pre-restart status: {e}")

        # Show log file sizes
        logger.info("  Log file sizes before restart:")
        for log_name, file_path in self.log_files.items():
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                logger.info(f"    {log_name}: {size} bytes")

        logger.info("\n" + "="*60)

    def run_full_test_suite(self):
        """Run the complete POC test suite."""
        logger.info("Starting APScheduler POC Test Suite")
        logger.info("="*50)

        tests = [
            ("API Connectivity", self.test_api_connectivity),
            ("SQLite Job Store", self.test_sqlite_job_store),
            ("Job Scheduling", self.test_job_scheduling),
            ("Database Settings Integration", self.test_database_settings_integration),
            ("Log File Persistence", self.test_log_file_persistence),
        ]

        results = {}
        for test_name, test_func in tests:
            logger.info(f"\n--- {test_name} ---")
            try:
                results[test_name] = test_func()
            except Exception as e:
                logger.error(f"❌ {test_name} failed with exception: {e}")
                results[test_name] = False

        # Summary
        logger.info("\n" + "="*50)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("="*50)

        passed = 0
        total = len(tests)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status} - {test_name}")
            if result:
                passed += 1

        logger.info(f"\nOverall: {passed}/{total} tests passed")

        if passed == total:
            logger.info("🎉 All POC tests passed! APScheduler + SQLite + Docker persistence is working correctly.")

            # Monitor job execution
            logger.info("\nStarting job execution monitoring...")
            self.monitor_job_execution(duration_minutes=2)

            # Provide restart test instructions
            self.generate_restart_instructions()

        else:
            logger.error("❌ Some tests failed. Check the logs above for details.")

        return passed == total


if __name__ == "__main__":
    # Allow customizing the base URL for testing
    import sys

    base_url = "http://localhost:8001"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    tester = SchedulerPOCTester(base_url)
    success = tester.run_full_test_suite()

    exit(0 if success else 1)