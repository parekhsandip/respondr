import os
import logging
from database.models import db, Ticket, Attachment, EmailSyncLog

logger = logging.getLogger(__name__)

def init_database(app):
    """Initialize database tables and directories"""
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")

            # Create storage directories
            attachment_dir = app.config.get('ATTACHMENT_STORAGE_PATH', 'storage/attachments')
            os.makedirs(attachment_dir, exist_ok=True)
            logger.info(f"Created attachment storage directory: {attachment_dir}")

            return True
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise

def create_sample_data(app):
    """Create sample data for development/testing"""
    from datetime import datetime, timedelta
    import random

    try:
        with app.app_context():
            # Check if we already have data
            if Ticket.query.count() > 0:
                logger.info("Sample data already exists, skipping creation")
                return

            sample_tickets = [
                {
                    'subject': 'Welcome to our service!',
                    'sender_email': 'support@example.com',
                    'sender_name': 'Support Team',
                    'content_text': 'Thank you for signing up for our service. We are excited to have you on board!',
                    'status': 'new'
                },
                {
                    'subject': 'Password reset request',
                    'sender_email': 'user@example.com',
                    'sender_name': 'John Doe',
                    'content_text': 'I forgot my password and need to reset it. Can you please help me?',
                    'status': 'read'
                },
                {
                    'subject': 'Bug report: Login issue',
                    'sender_email': 'developer@example.com',
                    'sender_name': 'Jane Smith',
                    'content_text': 'I am experiencing issues logging into the application. The login button does not respond.',
                    'status': 'new'
                },
                {
                    'subject': 'Feature request: Dark mode',
                    'sender_email': 'user2@example.com',
                    'sender_name': 'Bob Wilson',
                    'content_text': 'It would be great if you could add a dark mode option to the application.',
                    'status': 'archived'
                }
            ]

            for i, ticket_data in enumerate(sample_tickets):
                ticket = Ticket(
                    ticket_number=Ticket.create_unique_ticket_number(),
                    source='email',
                    source_id=f'sample-message-id-{i}@example.com',
                    subject=ticket_data['subject'],
                    content_text=ticket_data['content_text'],
                    sender_email=ticket_data['sender_email'],
                    sender_name=ticket_data['sender_name'],
                    recipient_email='support@respondr.local',
                    status=ticket_data['status'],
                    received_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72)),
                    priority=random.randint(1, 5)
                )
                db.session.add(ticket)

            db.session.commit()
            logger.info(f"Created {len(sample_tickets)} sample tickets")

    except Exception as e:
        logger.error(f"Sample data creation failed: {str(e)}")
        db.session.rollback()
        raise

def validate_database_schema(app):
    """Validate that the database schema is correct"""
    try:
        with app.app_context():
            # Check if tables exist by trying to query them
            Ticket.query.count()
            Attachment.query.count()
            EmailSyncLog.query.count()

            logger.info("Database schema validation passed")
            return True

    except Exception as e:
        logger.error(f"Database schema validation failed: {str(e)}")
        return False

def cleanup_old_logs(app, days_to_keep=30):
    """Clean up old sync logs"""
    from datetime import datetime, timedelta

    try:
        with app.app_context():
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            old_logs = EmailSyncLog.query.filter(EmailSyncLog.sync_time < cutoff_date).all()

            if old_logs:
                for log in old_logs:
                    db.session.delete(log)
                db.session.commit()
                logger.info(f"Cleaned up {len(old_logs)} old sync logs")
            else:
                logger.info("No old sync logs to clean up")

    except Exception as e:
        logger.error(f"Log cleanup failed: {str(e)}")
        raise