import os
import logging
from database.models import (
    db, Ticket, Attachment, EmailSyncLog, Settings,
    Agent, Organization, TicketType, Tag, Status, TicketReply, TicketFollower, ReplyAttachment, TicketRelationship, SavedFilter
)
from sqlalchemy import text

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
            Settings.query.count()
            Agent.query.count()
            Organization.query.count()
            TicketType.query.count()
            Tag.query.count()
            TicketReply.query.count()
            TicketFollower.query.count()
            ReplyAttachment.query.count()

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

def create_default_agents(app):
    """Create default system agents"""
    try:
        with app.app_context():
            # Check if we already have agents
            if Agent.query.count() > 0:
                logger.info("Agents already exist, skipping default creation")
                return

            # Create default admin agent
            admin_agent = Agent(
                username='admin',
                email='admin@respondr.local',
                first_name='System',
                last_name='Administrator',
                role='admin',
                is_active=True,
                timezone='UTC',
                language='en'
            )
            admin_agent.set_password('admin123')  # Should be changed in production
            db.session.add(admin_agent)

            # Create default support agent
            support_agent = Agent(
                username='support',
                email='support@respondr.local',
                first_name='Support',
                last_name='Agent',
                role='agent',
                is_active=True,
                timezone='UTC',
                language='en',
                signature='Best regards,\nSupport Team'
            )
            support_agent.set_password('support123')  # Should be changed in production
            db.session.add(support_agent)

            db.session.commit()
            logger.info("Created default agents: admin and support")

    except Exception as e:
        logger.error(f"Default agents creation failed: {str(e)}")
        db.session.rollback()
        raise

def create_default_ticket_types(app):
    """Create default ticket types"""
    try:
        with app.app_context():
            # Check if we already have ticket types
            if TicketType.query.count() > 0:
                logger.info("Ticket types already exist, skipping default creation")
                return

            default_types = [
                {
                    'name': 'General Inquiry',
                    'description': 'General questions and inquiries',
                    'color': '#6B7280',
                    'icon': 'question-mark-circle',
                    'default_priority': 3,
                    'sort_order': 1
                },
                {
                    'name': 'Bug Report',
                    'description': 'Software bugs and technical issues',
                    'color': '#DC2626',
                    'icon': 'exclamation-triangle',
                    'default_priority': 2,
                    'sort_order': 2
                },
                {
                    'name': 'Feature Request',
                    'description': 'Requests for new features or enhancements',
                    'color': '#059669',
                    'icon': 'light-bulb',
                    'default_priority': 4,
                    'sort_order': 3
                },
                {
                    'name': 'Support Request',
                    'description': 'Customer support and help requests',
                    'color': '#2563EB',
                    'icon': 'support',
                    'default_priority': 3,
                    'sort_order': 4
                },
                {
                    'name': 'Account Issue',
                    'description': 'Account-related problems and questions',
                    'color': '#DC2626',
                    'icon': 'user-circle',
                    'default_priority': 2,
                    'sort_order': 5
                },
                {
                    'name': 'Billing',
                    'description': 'Billing and payment related inquiries',
                    'color': '#D97706',
                    'icon': 'credit-card',
                    'default_priority': 3,
                    'sort_order': 6
                }
            ]

            for type_data in default_types:
                ticket_type = TicketType(
                    name=type_data['name'],
                    description=type_data['description'],
                    color=type_data['color'],
                    icon=type_data['icon'],
                    default_priority=type_data['default_priority'],
                    sort_order=type_data['sort_order'],
                    is_active=True
                )
                db.session.add(ticket_type)

            db.session.commit()
            logger.info(f"Created {len(default_types)} default ticket types")

    except Exception as e:
        logger.error(f"Default ticket types creation failed: {str(e)}")
        db.session.rollback()
        raise

def create_default_tags(app):
    """Create default tags"""
    try:
        with app.app_context():
            # Check if we already have tags
            if Tag.query.count() > 0:
                logger.info("Tags already exist, skipping default creation")
                return

            default_tags = [
                {'name': 'urgent', 'description': 'Urgent priority items', 'color': '#DC2626'},
                {'name': 'customer', 'description': 'Customer-facing issues', 'color': '#2563EB'},
                {'name': 'internal', 'description': 'Internal team issues', 'color': '#6B7280'},
                {'name': 'security', 'description': 'Security-related concerns', 'color': '#DC2626'},
                {'name': 'performance', 'description': 'Performance and optimization', 'color': '#D97706'},
                {'name': 'mobile', 'description': 'Mobile app related', 'color': '#059669'},
                {'name': 'web', 'description': 'Web application related', 'color': '#2563EB'},
                {'name': 'api', 'description': 'API related issues', 'color': '#7C3AED'},
                {'name': 'documentation', 'description': 'Documentation improvements', 'color': '#059669'},
                {'name': 'training', 'description': 'Training and education needs', 'color': '#D97706'}
            ]

            for tag_data in default_tags:
                tag = Tag(
                    name=tag_data['name'],
                    description=tag_data['description'],
                    color=tag_data['color'],
                    is_active=True
                )
                db.session.add(tag)

            db.session.commit()
            logger.info(f"Created {len(default_tags)} default tags")

    except Exception as e:
        logger.error(f"Default tags creation failed: {str(e)}")
        db.session.rollback()
        raise

def create_default_statuses(app):
    """Create default statuses matching existing ticket statuses"""
    try:
        with app.app_context():
            # Check if we already have statuses
            if Status.query.count() > 0:
                logger.info("Statuses already exist, skipping default creation")
                return

            default_statuses = [
                {
                    'name': 'New',
                    'description': 'New tickets that have not been reviewed',
                    'color': '#3B82F6',  # Blue
                    'is_closed_status': False,
                    'display_order': 1
                },
                {
                    'name': 'Open',
                    'description': 'Tickets that are actively being worked on',
                    'color': '#10B981',  # Green
                    'is_closed_status': False,
                    'display_order': 2
                },
                {
                    'name': 'Pending',
                    'description': 'Tickets awaiting customer response or external input',
                    'color': '#F59E0B',  # Amber
                    'is_closed_status': False,
                    'display_order': 3
                },
                {
                    'name': 'On Hold',
                    'description': 'Tickets temporarily paused',
                    'color': '#6B7280',  # Gray
                    'is_closed_status': False,
                    'display_order': 4
                },
                {
                    'name': 'Solved',
                    'description': 'Tickets that have been resolved',
                    'color': '#059669',  # Emerald
                    'is_closed_status': True,
                    'display_order': 5
                },
                {
                    'name': 'Closed',
                    'description': 'Tickets that are fully closed and archived',
                    'color': '#6B7280',  # Gray
                    'is_closed_status': True,
                    'display_order': 6
                }
            ]

            for status_data in default_statuses:
                status = Status(
                    name=status_data['name'],
                    description=status_data['description'],
                    color=status_data['color'],
                    is_closed_status=status_data['is_closed_status'],
                    display_order=status_data['display_order'],
                    is_active=True
                )
                db.session.add(status)

            db.session.commit()
            logger.info(f"Created {len(default_statuses)} default statuses")

    except Exception as e:
        logger.error(f"Default statuses creation failed: {str(e)}")
        db.session.rollback()
        raise

def create_default_organizations(app):
    """Create default organizations"""
    try:
        with app.app_context():
            # Check if we already have organizations
            if Organization.query.count() > 0:
                logger.info("Organizations already exist, skipping default creation")
                return

            default_orgs = [
                {
                    'name': 'Example Corporation',
                    'domain': 'example.com',
                    'description': 'A sample organization for testing',
                    'website': 'https://www.example.com',
                    'industry': 'Technology',
                    'size': 'medium'
                },
                {
                    'name': 'Demo Company',
                    'domain': 'demo.com',
                    'description': 'Demo organization for development',
                    'website': 'https://www.demo.com',
                    'industry': 'Services',
                    'size': 'small'
                }
            ]

            for org_data in default_orgs:
                org = Organization(
                    name=org_data['name'],
                    domain=org_data['domain'],
                    description=org_data['description'],
                    website=org_data['website'],
                    industry=org_data['industry'],
                    size=org_data['size'],
                    is_active=True
                )
                db.session.add(org)

            db.session.commit()
            logger.info(f"Created {len(default_orgs)} default organizations")

    except Exception as e:
        logger.error(f"Default organizations creation failed: {str(e)}")
        db.session.rollback()
        raise

def run_full_migration(app):
    """Run complete migration with all components"""
    try:
        logger.info("Starting full database migration...")

        # Initialize database tables
        init_database(app)

        # Initialize default settings
        with app.app_context():
            from database.models import Settings
            Settings.initialize_defaults()

        # Create default data
        create_default_agents(app)
        create_default_ticket_types(app)
        create_default_tags(app)
        create_default_statuses(app)
        create_default_organizations(app)

        # Create sample tickets (optional)
        create_sample_data(app)

        # Validate schema
        if validate_database_schema(app):
            logger.info("Full database migration completed successfully!")
            return True
        else:
            logger.error("Migration validation failed!")
            return False

    except Exception as e:
        logger.error(f"Full migration failed: {str(e)}")
        raise

def migrate_existing_tickets(app):
    """Migrate existing tickets to new schema (for upgrading existing installations)"""
    try:
        with app.app_context():
            # Get default values for new fields
            default_agent = Agent.query.filter_by(role='agent').first()
            general_type = TicketType.query.filter_by(name='General Inquiry').first()

            tickets = Ticket.query.all()
            for ticket in tickets:
                # Set default values for new fields if they don't exist
                if not hasattr(ticket, 'channel') or ticket.channel is None:
                    ticket.channel = 'email'
                if not hasattr(ticket, 'language') or ticket.language is None:
                    ticket.language = 'en'
                if not hasattr(ticket, 'urgency') or ticket.urgency is None:
                    ticket.urgency = 3
                if not hasattr(ticket, 'escalation_level') or ticket.escalation_level is None:
                    ticket.escalation_level = 0

                # Try to assign to default agent if no assignee
                if not ticket.assignee_id and default_agent:
                    ticket.assignee_id = default_agent.id

                # Try to set default type if no type
                if not ticket.type_id and general_type:
                    ticket.type_id = general_type.id

            db.session.commit()
            logger.info(f"Migrated {len(tickets)} existing tickets to new schema")

    except Exception as e:
        logger.error(f"Ticket migration failed: {str(e)}")
        db.session.rollback()
        raise

def migrate_add_read_status(app):
    """Add read status columns to tickets table"""
    try:
        with app.app_context():
            # Check if columns already exist
            with db.engine.connect() as connection:
                result = connection.execute(text("PRAGMA table_info(tickets)"))
                columns = [row[1] for row in result]

                if 'is_read' not in columns:
                    logger.info("Adding is_read column to tickets table")
                    connection.execute(text("ALTER TABLE tickets ADD COLUMN is_read BOOLEAN DEFAULT 0 NOT NULL"))

                if 'first_read_at' not in columns:
                    logger.info("Adding first_read_at column to tickets table")
                    connection.execute(text("ALTER TABLE tickets ADD COLUMN first_read_at DATETIME"))

                connection.commit()
                logger.info("Read status migration completed successfully")

    except Exception as e:
        logger.error(f"Read status migration failed: {str(e)}")
        raise

def migrate_add_soft_delete(app):
    """Add soft delete columns to tickets table"""
    try:
        with app.app_context():
            # Check if columns already exist
            with db.engine.connect() as connection:
                result = connection.execute(text("PRAGMA table_info(tickets)"))
                columns = [row[1] for row in result]

                if 'is_deleted' not in columns:
                    logger.info("Adding is_deleted column to tickets table")
                    connection.execute(text("ALTER TABLE tickets ADD COLUMN is_deleted BOOLEAN DEFAULT 0 NOT NULL"))

                if 'deleted_at' not in columns:
                    logger.info("Adding deleted_at column to tickets table")
                    connection.execute(text("ALTER TABLE tickets ADD COLUMN deleted_at DATETIME"))

                if 'deleted_by' not in columns:
                    logger.info("Adding deleted_by column to tickets table")
                    connection.execute(text("ALTER TABLE tickets ADD COLUMN deleted_by INTEGER"))

                connection.commit()
                logger.info("Soft delete migration completed successfully")

    except Exception as e:
        logger.error(f"Soft delete migration failed: {str(e)}")
        raise

def migrate_add_saved_filters(app):
    """Create saved_filters table"""
    try:
        with app.app_context():
            # Check if table already exists
            with db.engine.connect() as connection:
                result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='saved_filters'"))
                table_exists = result.fetchone() is not None

                if not table_exists:
                    logger.info("Creating saved_filters table")
                    # Create all tables (this will create only missing tables)
                    db.create_all()
                    logger.info("Saved filters table created successfully")
                else:
                    logger.info("Saved filters table already exists")

    except Exception as e:
        logger.error(f"Saved filters migration failed: {str(e)}")
        raise