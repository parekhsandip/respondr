import os
import logging
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from datetime import datetime
import hashlib
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from config import Config
from database.models import db, Ticket, Attachment, EmailSyncLog, Settings
from services.email_fetcher import EmailFetcher
from services.ticket_service import TicketService

def migrate_env_to_settings():
    """Migrate settings from environment variables to database if database is empty"""
    try:
        # Check if settings are already populated
        if Settings.query.count() > 0:
            # Settings exist, check if we should update from .env
            existing_username = Settings.get('IMAP_USERNAME')
            env_username = os.environ.get('IMAP_USERNAME', '')

            # If .env has credentials but database doesn't, migrate
            if env_username and not existing_username:
                logger.info("Migrating email credentials from .env to database")
                migrate_email_settings()
            return

        logger.info("Initializing settings from environment variables")

        # Migrate email settings
        migrate_email_settings()

        # Migrate sync settings
        if os.environ.get('FETCH_INTERVAL'):
            Settings.set('FETCH_INTERVAL', os.environ.get('FETCH_INTERVAL'), category='sync')
        if os.environ.get('MAX_EMAILS_PER_SYNC'):
            Settings.set('MAX_EMAILS_PER_SYNC', os.environ.get('MAX_EMAILS_PER_SYNC'), category='sync')
        if os.environ.get('SCHEDULER_ENABLED'):
            Settings.set('SCHEDULER_ENABLED', os.environ.get('SCHEDULER_ENABLED'), category='sync')

        # Migrate file settings
        if os.environ.get('ATTACHMENT_MAX_SIZE'):
            Settings.set('ATTACHMENT_MAX_SIZE', os.environ.get('ATTACHMENT_MAX_SIZE'), category='files')
        if os.environ.get('ATTACHMENT_STORAGE_PATH'):
            Settings.set('ATTACHMENT_STORAGE_PATH', os.environ.get('ATTACHMENT_STORAGE_PATH'), category='files')

        # Migrate app settings
        if os.environ.get('TICKETS_PER_PAGE'):
            Settings.set('TICKETS_PER_PAGE', os.environ.get('TICKETS_PER_PAGE'), category='app')

        logger.info("Environment variable migration completed")

    except Exception as e:
        logger.error(f"Failed to migrate environment variables: {str(e)}")

def migrate_email_settings():
    """Migrate email-specific settings from environment"""
    email_vars = [
        'IMAP_SERVER', 'IMAP_PORT', 'IMAP_USERNAME', 'IMAP_PASSWORD',
        'IMAP_USE_SSL', 'IMAP_FOLDER', 'SMTP_SERVER', 'SMTP_PORT'
    ]

    for var in email_vars:
        env_value = os.environ.get(var)
        if env_value:
            Settings.set(var, env_value, category='email')

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)

    # Initialize scheduler
    scheduler = APScheduler()
    scheduler.init_app(app)

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Add built-in functions to Jinja2 templates
    app.jinja_env.globals.update(min=min, max=max)

    # Initialize services
    email_fetcher = EmailFetcher(app.config)
    ticket_service = TicketService()

    @app.route('/')
    def index():
        """Dashboard/inbox view"""
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '')

        query = Ticket.query

        if status_filter and status_filter != 'all':
            query = query.filter_by(status=status_filter)

        if search_query:
            query = query.filter(
                db.or_(
                    Ticket.subject.contains(search_query),
                    Ticket.sender_name.contains(search_query),
                    Ticket.sender_email.contains(search_query),
                    Ticket.content_text.contains(search_query)
                )
            )

        tickets = query.order_by(Ticket.received_at.desc()).paginate(
            page=page, per_page=20, error_out=False
        )

        return render_template('inbox.html', tickets=tickets, status_filter=status_filter, search_query=search_query)

    @app.route('/tickets')
    def tickets_list():
        """API endpoint for HTMX ticket list updates"""
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '')

        query = Ticket.query

        if status_filter and status_filter != 'all':
            query = query.filter_by(status=status_filter)

        if search_query:
            query = query.filter(
                db.or_(
                    Ticket.subject.contains(search_query),
                    Ticket.sender_name.contains(search_query),
                    Ticket.sender_email.contains(search_query),
                    Ticket.content_text.contains(search_query)
                )
            )

        tickets = query.order_by(Ticket.received_at.desc()).paginate(
            page=page, per_page=20, error_out=False
        )

        return render_template('components/ticket_list.html', tickets=tickets)

    @app.route('/ticket/<int:ticket_id>')
    def ticket_view(ticket_id):
        """View single ticket"""
        ticket = Ticket.query.get_or_404(ticket_id)
        attachments = Attachment.query.filter_by(ticket_id=ticket_id).all()

        # Mark as read if it's not already
        if ticket.status == 'new':
            ticket.status = 'read'
            ticket.updated_at = datetime.utcnow()
            db.session.commit()

        return render_template('ticket_view.html', ticket=ticket, attachments=attachments)

    @app.route('/attachment/<int:attachment_id>')
    def download_attachment(attachment_id):
        """Download attachment"""
        attachment = Attachment.query.get_or_404(attachment_id)

        try:
            return send_file(
                attachment.storage_path,
                as_attachment=True,
                download_name=attachment.filename,
                mimetype=attachment.content_type
            )
        except FileNotFoundError:
            logger.error(f"Attachment file not found: {attachment.storage_path}")
            return jsonify({'error': 'File not found'}), 404

    @app.route('/api/sync', methods=['POST'])
    def manual_sync():
        """Manual sync trigger"""
        try:
            result = email_fetcher.fetch_new_emails()
            return jsonify({
                'success': True,
                'emails_fetched': result.get('emails_fetched', 0),
                'message': 'Sync completed successfully'
            })
        except Exception as e:
            logger.error(f"Manual sync failed: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Sync failed: {str(e)}'
            }), 500

    @app.route('/api/ticket/<int:ticket_id>/mark-read', methods=['POST'])
    def mark_ticket_read(ticket_id):
        """Mark ticket as read"""
        ticket = Ticket.query.get_or_404(ticket_id)
        ticket.status = 'read'
        ticket.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'status': 'read'})

    @app.route('/api/ticket/<int:ticket_id>/mark-unread', methods=['POST'])
    def mark_ticket_unread(ticket_id):
        """Mark ticket as unread"""
        ticket = Ticket.query.get_or_404(ticket_id)
        ticket.status = 'new'
        ticket.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'status': 'new'})

    @app.route('/api/ticket/<int:ticket_id>/archive', methods=['POST'])
    def archive_ticket(ticket_id):
        """Archive ticket"""
        ticket = Ticket.query.get_or_404(ticket_id)
        ticket.status = 'archived'
        ticket.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'status': 'archived'})

    @app.route('/settings')
    def settings():
        """Email configuration page"""
        return render_template('settings.html')

    @app.route('/api/test-connection', methods=['POST'])
    def test_email_connection():
        """Test email connection"""
        try:
            # Refresh email fetcher settings before testing
            email_fetcher.refresh_settings()
            result = email_fetcher.test_connection()
            return jsonify({'success': True, 'message': 'Connection successful'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

    @app.route('/api/settings', methods=['GET'])
    def get_settings():
        """Get all settings by category"""
        try:
            category = request.args.get('category', 'all')
            if category == 'all':
                settings = {}
                for cat in ['email', 'sync', 'files', 'app']:
                    settings[cat] = {s.key: s.value for s in Settings.get_by_category(cat)}
            else:
                settings = {s.key: s.value for s in Settings.get_by_category(category)}

            return jsonify({'success': True, 'settings': settings})
        except Exception as e:
            logger.error(f"Failed to get settings: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/settings', methods=['POST'])
    def save_settings():
        """Save settings to database"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No data provided'}), 400

            saved_count = 0
            for category, settings in data.items():
                if isinstance(settings, dict):
                    for key, value in settings.items():
                        Settings.set(key, value, category=category)
                        saved_count += 1

            # Refresh email fetcher settings after saving
            email_fetcher.refresh_settings()

            return jsonify({
                'success': True,
                'message': f'Saved {saved_count} settings',
                'count': saved_count
            })
        except Exception as e:
            logger.error(f"Failed to save settings: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/settings/<category>', methods=['GET'])
    def get_settings_by_category(category):
        """Get settings for a specific category"""
        try:
            settings = {s.key: s.value for s in Settings.get_by_category(category)}
            return jsonify({'success': True, 'settings': settings})
        except Exception as e:
            logger.error(f"Failed to get {category} settings: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/settings/<category>', methods=['POST'])
    def save_settings_by_category(category):
        """Save settings for a specific category"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No data provided'}), 400

            saved_count = 0
            for key, value in data.items():
                Settings.set(key, value, category=category)
                saved_count += 1

            # Refresh email fetcher settings if email category was updated
            if category == 'email':
                email_fetcher.refresh_settings()

            return jsonify({
                'success': True,
                'message': f'Saved {saved_count} {category} settings',
                'count': saved_count
            })
        except Exception as e:
            logger.error(f"Failed to save {category} settings: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500


    def sync_emails():
        """Background task to sync emails"""
        with app.app_context():
            try:
                logger.info("Starting scheduled email sync")
                result = email_fetcher.fetch_new_emails()
                logger.info(f"Sync completed: {result.get('emails_fetched', 0)} emails fetched")
            except Exception as e:
                logger.error(f"Scheduled sync failed: {str(e)}")

    # Schedule background email fetching
    if app.config.get('SCHEDULER_ENABLED', True):
        scheduler.add_job(
            func=sync_emails,
            trigger="interval",
            seconds=app.config.get('FETCH_INTERVAL', 300),
            id='email_sync'
        )
        scheduler.start()

    # Create tables and initialize settings
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")

        # Initialize default settings
        Settings.initialize_defaults()

        # Migrate settings from .env if they exist and database settings are empty
        migrate_env_to_settings()
        logger.info("Settings initialized")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5001)