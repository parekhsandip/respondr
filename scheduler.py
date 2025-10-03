#!/usr/bin/env python3
"""
Standalone Email Sync Scheduler

This script runs the email synchronization as a separate process,
independent of the main Flask application.

Usage:
    python scheduler.py                    # Run with default settings
    python scheduler.py --interval 300     # Custom interval in seconds
    python scheduler.py --once             # Run once and exit
"""

import os
import sys
import time
import signal
import logging
import argparse
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from services.email_fetcher import EmailFetcher

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/scheduler.log')
    ]
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    logger.info(f"Received signal {signum}. Shutting down gracefully...")
    running = False


def sync_emails(app):
    """Sync emails with application context"""
    with app.app_context():
        try:
            logger.info("=" * 60)
            logger.info(f"Starting scheduled email sync at {datetime.now()}")

            email_fetcher = EmailFetcher()
            result = email_fetcher.fetch_new_emails()

            emails_fetched = result.get('emails_fetched', 0)
            errors = result.get('errors', [])

            logger.info(f"Sync completed: {emails_fetched} emails fetched")

            if errors:
                logger.warning(f"Encountered {len(errors)} errors during sync:")
                for error in errors:
                    logger.warning(f"  - {error}")

            logger.info("=" * 60)
            return result

        except Exception as e:
            logger.error(f"Scheduled sync failed: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}


def run_once(app):
    """Run email sync once and exit"""
    logger.info("Running email sync once...")
    result = sync_emails(app)

    # Check if result exists and has success or emails_fetched
    if result and (result.get('success') or 'emails_fetched' in result):
        logger.info("One-time sync completed successfully")
        sys.exit(0)
    else:
        logger.error("One-time sync failed")
        sys.exit(1)


def run_scheduler(app, interval):
    """Run scheduler in a loop"""
    global running

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create scheduler
    scheduler = BackgroundScheduler()

    # Add job
    scheduler.add_job(
        func=lambda: sync_emails(app),
        trigger=IntervalTrigger(seconds=interval),
        id='email_sync',
        name='Email Sync Job',
        replace_existing=True
    )

    logger.info(f"Starting email sync scheduler with {interval} second interval")
    scheduler.start()

    # Run initial sync immediately
    logger.info("Running initial email sync...")
    sync_emails(app)

    # Keep the scheduler running
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Standalone Email Sync Scheduler for Respondr'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Sync interval in seconds (default: 300)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run sync once and exit'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Create Flask app
    logger.info("Initializing Flask application...")
    app = create_app()

    # Ensure scheduler is disabled in app (we're running it separately)
    app.config['SCHEDULER_ENABLED'] = False

    logger.info(f"Application initialized successfully")
    logger.info(f"Database: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

    # Run based on mode
    if args.once:
        run_once(app)
    else:
        run_scheduler(app, args.interval)


if __name__ == '__main__':
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    try:
        main()
    except Exception as e:
        logger.error(f"Scheduler crashed: {str(e)}", exc_info=True)
        sys.exit(1)
