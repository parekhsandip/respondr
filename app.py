import os
import logging
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import hashlib
from dotenv import load_dotenv
from collections import defaultdict
import time

# Load environment variables from .env file
load_dotenv()

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from config import Config
from database.models import (
    db, Ticket, Attachment, EmailSyncLog, Settings,
    Agent, Organization, TicketType, Tag, Status, TicketReply, TicketFollower, ReplyAttachment, TicketActivity,
    TicketRelationship, ticket_tags, SavedFilter
)
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

    # Simple rate limiter for widget submissions
    widget_rate_limiter = defaultdict(list)
    RATE_LIMIT_WINDOW = 300  # 5 minutes in seconds
    RATE_LIMIT_MAX_REQUESTS = 5  # Max 5 submissions per 5 minutes per IP

    def is_rate_limited(ip_address):
        """Check if an IP address is rate limited"""
        current_time = time.time()
        # Clean old entries
        widget_rate_limiter[ip_address] = [
            timestamp for timestamp in widget_rate_limiter[ip_address]
            if current_time - timestamp < RATE_LIMIT_WINDOW
        ]

        # Check if rate limit exceeded
        if len(widget_rate_limiter[ip_address]) >= RATE_LIMIT_MAX_REQUESTS:
            return True

        # Add current request
        widget_rate_limiter[ip_address].append(current_time)
        return False

    def sanitize_input(text):
        """Basic input sanitization to prevent XSS and other attacks"""
        if not text:
            return text

        # Remove potentially dangerous characters
        import html
        text = html.escape(text)

        # Remove control characters except newlines and tabs
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')

        # Limit length
        return text[:10000] if text else text

    # Add built-in functions to Jinja2 templates
    app.jinja_env.globals.update(min=min, max=max)

    # Cache busting versioning system
    def asset_version(filename):
        """Generate version string for static assets based on file modification time"""
        try:
            asset_path = os.path.join(app.static_folder, filename)
            if os.path.exists(asset_path):
                mtime = os.path.getmtime(asset_path)
                return str(int(mtime))
            return "1"
        except:
            return "1"

    app.jinja_env.globals['asset_version'] = asset_version

    # Initialize services
    email_fetcher = EmailFetcher(app.config)
    ticket_service = TicketService()

    @app.route('/')
    def index():
        """Dashboard/inbox view with comprehensive search and filtering"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        # Search and filter parameters
        search_query = request.args.get('search', '')
        status_filter = request.args.get('status', 'all')
        assignee_filter = request.args.get('assignee', 'all')
        type_filter = request.args.get('type', 'all')
        priority_filter = request.args.get('priority', 'all')
        organization_filter = request.args.get('organization', 'all')
        tag_filter = request.args.get('tag', 'all')
        unassigned_filter = request.args.get('unassigned') == 'true'

        # Date filters
        created_from = request.args.get('created_from')
        created_to = request.args.get('created_to')

        # Sorting
        sort_by = request.args.get('sort', 'updated')
        sort_order = request.args.get('order', 'desc')

        query = Ticket.query.filter(Ticket.is_deleted == False)

        # Join with related tables for sorting/filtering
        query = query.outerjoin(Agent, Ticket.assignee_id == Agent.id) \
                     .outerjoin(Organization, Ticket.organization_id == Organization.id) \
                     .outerjoin(TicketType, Ticket.type_id == TicketType.id)

        # Apply filters
        if status_filter and status_filter != 'all':
            query = query.filter(Ticket.status == status_filter)

        if assignee_filter and assignee_filter != 'all':
            query = query.filter(Ticket.assignee_id == assignee_filter)

        if unassigned_filter:
            query = query.filter(Ticket.assignee_id.is_(None))

        if type_filter and type_filter != 'all':
            query = query.filter(Ticket.type_id == type_filter)

        if priority_filter and priority_filter != 'all':
            query = query.filter(Ticket.priority == priority_filter)

        if organization_filter and organization_filter != 'all':
            query = query.filter(Ticket.organization_id == organization_filter)

        # Tag filtering
        if tag_filter and tag_filter != 'all':
            query = query.join(ticket_tags).filter(ticket_tags.c.tag_id == tag_filter)

        # Date range filtering
        if created_from:
            try:
                from_date = datetime.strptime(created_from, '%Y-%m-%d').date()
                query = query.filter(Ticket.created_at >= from_date)
            except ValueError:
                pass

        if created_to:
            try:
                to_date = datetime.strptime(created_to, '%Y-%m-%d').date()
                # Add one day to include the entire end date
                to_date = datetime.combine(to_date, datetime.min.time()) + timedelta(days=1)
                query = query.filter(Ticket.created_at < to_date)
            except ValueError:
                pass

        # Text search
        if search_query:
            search_filter = db.or_(
                Ticket.subject.contains(search_query),
                Ticket.sender_name.contains(search_query),
                Ticket.sender_email.contains(search_query),
                Ticket.content_text.contains(search_query),
                Ticket.ticket_number.contains(search_query),
                Organization.name.contains(search_query),
                Agent.first_name.contains(search_query),
                Agent.last_name.contains(search_query)
            )
            query = query.filter(search_filter)

        # Apply sorting
        sort_options = {
            'status': Ticket.status,
            'subject': Ticket.subject,
            'requester': Ticket.sender_name,
            'assignee': Agent.first_name,
            'type': TicketType.name,
            'priority': Ticket.priority,
            'updated': db.case(
                (Ticket.updated_at.isnot(None), Ticket.updated_at),
                else_=Ticket.created_at
            ),
        }

        sort_column = sort_options.get(sort_by, Ticket.created_at)
        if sort_order == 'asc':
            sort_column = sort_column.asc()
        else:
            sort_column = sort_column.desc()

        query = query.order_by(sort_column)

        tickets = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Get filter options for dropdowns
        agents = Agent.query.filter_by(is_active=True).all()
        ticket_types = TicketType.query.filter_by(is_active=True).all()
        organizations = Organization.query.all()
        tags = Tag.query.filter_by(is_active=True).all()

        # Create filter context
        filters = {
            'search': search_query,
            'status': status_filter,
            'assignee': assignee_filter,
            'type': type_filter,
            'priority': priority_filter,
            'organization': organization_filter,
            'tag': tag_filter,
            'unassigned': unassigned_filter,
            'created_from': created_from,
            'created_to': created_to,
            'sort': sort_by,
            'order': sort_order
        }

        return render_template('inbox.html',
                             tickets=tickets,
                             status_filter=status_filter,
                             search_query=search_query,
                             filters=filters,
                             agents=agents,
                             ticket_types=ticket_types,
                             organizations=organizations,
                             tags=tags)

    @app.route('/tickets')
    def tickets_list():
        """API endpoint for HTMX ticket list updates with comprehensive filtering"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        # Search and filter parameters (same as index)
        search_query = request.args.get('search', '')
        status_filter = request.args.get('status', 'all')
        assignee_filter = request.args.get('assignee', 'all')
        type_filter = request.args.get('type', 'all')
        priority_filter = request.args.get('priority', 'all')
        organization_filter = request.args.get('organization', 'all')
        tag_filter = request.args.get('tag', 'all')
        unassigned_filter = request.args.get('unassigned') == 'true'

        # Date filters
        created_from = request.args.get('created_from')
        created_to = request.args.get('created_to')

        # Sorting
        sort_by = request.args.get('sort', 'updated')
        sort_order = request.args.get('order', 'desc')

        query = Ticket.query

        # Join with related tables for sorting/filtering
        query = query.outerjoin(Agent, Ticket.assignee_id == Agent.id) \
                     .outerjoin(Organization, Ticket.organization_id == Organization.id) \
                     .outerjoin(TicketType, Ticket.type_id == TicketType.id)

        # Apply same filters as index
        if status_filter and status_filter != 'all':
            query = query.filter(Ticket.status == status_filter)

        if assignee_filter and assignee_filter != 'all':
            query = query.filter(Ticket.assignee_id == assignee_filter)

        if unassigned_filter:
            query = query.filter(Ticket.assignee_id.is_(None))

        if type_filter and type_filter != 'all':
            query = query.filter(Ticket.type_id == type_filter)

        if priority_filter and priority_filter != 'all':
            query = query.filter(Ticket.priority == priority_filter)

        if organization_filter and organization_filter != 'all':
            query = query.filter(Ticket.organization_id == organization_filter)

        if tag_filter and tag_filter != 'all':
            query = query.join(ticket_tags).filter(ticket_tags.c.tag_id == tag_filter)

        # Date range filtering
        if created_from:
            try:
                from_date = datetime.strptime(created_from, '%Y-%m-%d').date()
                query = query.filter(Ticket.created_at >= from_date)
            except ValueError:
                pass

        if created_to:
            try:
                to_date = datetime.strptime(created_to, '%Y-%m-%d').date()
                to_date = datetime.combine(to_date, datetime.min.time()) + timedelta(days=1)
                query = query.filter(Ticket.created_at < to_date)
            except ValueError:
                pass

        # Text search
        if search_query:
            search_filter = db.or_(
                Ticket.subject.contains(search_query),
                Ticket.sender_name.contains(search_query),
                Ticket.sender_email.contains(search_query),
                Ticket.content_text.contains(search_query),
                Ticket.ticket_number.contains(search_query),
                Organization.name.contains(search_query),
                Agent.first_name.contains(search_query),
                Agent.last_name.contains(search_query)
            )
            query = query.filter(search_filter)

        # Apply sorting
        sort_options = {
            'status': Ticket.status,
            'subject': Ticket.subject,
            'requester': Ticket.sender_name,
            'assignee': Agent.first_name,
            'type': TicketType.name,
            'priority': Ticket.priority,
            'updated': db.case(
                (Ticket.updated_at.isnot(None), Ticket.updated_at),
                else_=Ticket.created_at
            ),
        }

        sort_column = sort_options.get(sort_by, Ticket.created_at)
        if sort_order == 'asc':
            sort_column = sort_column.asc()
        else:
            sort_column = sort_column.desc()

        query = query.order_by(sort_column)

        tickets = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return render_template('components/ticket_table.html',
                             tickets=tickets,
                             status_filter=status_filter,
                             search_query=search_query)

    @app.route('/ticket/<int:ticket_id>')
    def ticket_view(ticket_id):
        """View single ticket"""
        ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
        attachments = Attachment.query.filter_by(ticket_id=ticket_id).all()

        # Get additional data for the new template
        agents = Agent.query.filter_by(is_active=True).order_by(Agent.first_name).all()
        ticket_types = TicketType.query.filter_by(is_active=True).order_by(TicketType.sort_order).all()
        tags = Tag.query.filter_by(is_active=True).order_by(Tag.name).all()

        # Get replies in chronological order
        replies = TicketReply.query.filter_by(ticket_id=ticket_id).order_by(TicketReply.created_at.asc()).all()

        # Mark as read when ticket is viewed
        if not ticket.is_read:
            ticket.mark_as_read(agent_id=None)  # No agent ID since auto-marked on view

        # Use modern view by default, fallback to old view with query param
        template = 'ticket_view_modern.html' if request.args.get('view') != 'classic' else 'ticket_view.html'

        return render_template(template,
                             ticket=ticket,
                             attachments=attachments,
                             agents=agents,
                             ticket_types=ticket_types,
                             tags=tags,
                             replies=replies)

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
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            ticket.mark_as_read(agent_id=None)  # TODO: Pass actual agent ID when auth is implemented

            return jsonify({
                'success': True,
                'is_read': True,
                'first_read_at': ticket.first_read_at.isoformat() if ticket.first_read_at else None
            })
        except Exception as e:
            logger.error(f"Failed to mark ticket as read: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/mark-unread', methods=['POST'])
    def mark_ticket_unread(ticket_id):
        """Mark ticket as unread"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            ticket.mark_as_unread(agent_id=None)  # TODO: Pass actual agent ID when auth is implemented

            return jsonify({
                'success': True,
                'is_read': False
            })
        except Exception as e:
            logger.error(f"Failed to mark ticket as unread: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/delete', methods=['POST'])
    def delete_ticket(ticket_id):
        """Soft delete ticket"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            ticket.soft_delete(agent_id=None)  # TODO: Pass actual agent ID when auth is implemented

            return jsonify({
                'success': True,
                'message': 'Ticket deleted successfully',
                'is_deleted': True,
                'deleted_at': ticket.deleted_at.isoformat() if ticket.deleted_at else None
            })
        except Exception as e:
            logger.error(f"Failed to delete ticket: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/restore', methods=['POST'])
    def restore_ticket(ticket_id):
        """Restore soft-deleted ticket"""
        try:
            # For restore, we need to query deleted tickets
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == True).first_or_404()
            ticket.restore(agent_id=None)  # TODO: Pass actual agent ID when auth is implemented

            return jsonify({
                'success': True,
                'message': 'Ticket restored successfully',
                'is_deleted': False
            })
        except Exception as e:
            logger.error(f"Failed to restore ticket: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/archive', methods=['POST'])
    def archive_ticket(ticket_id):
        """Archive ticket"""
        ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
        ticket.status = 'archived'
        ticket.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'status': 'archived'})

    @app.route('/settings')
    def settings():
        """Redirect to new settings dashboard"""
        return redirect(url_for('settings_dashboard'))

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

    # Settings Dashboard Routes
    @app.route('/settings/<category>')
    def settings_category(category):
        """Settings category pages"""
        valid_categories = ['system', 'agents', 'organizations', 'ticket-types', 'tags', 'statuses', 'integrations']
        if category not in valid_categories:
            return redirect(url_for('settings'))

        return render_template(f'settings/{category}.html', active_category=category)

    @app.route('/settings/dashboard')
    def settings_dashboard():
        """Main settings dashboard"""
        return render_template('settings/index.html')

    # ============ COMPREHENSIVE TICKET MANAGEMENT API ENDPOINTS ============

    # Agent Management Endpoints
    @app.route('/api/agents', methods=['GET'])
    def get_agents():
        """Get all active agents"""
        try:
            agents = Agent.query.filter_by(is_active=True).all()
            return jsonify({
                'success': True,
                'agents': [{
                    'id': agent.id,
                    'username': agent.username,
                    'email': agent.email,
                    'full_name': agent.full_name,
                    'role': agent.role,
                    'avatar_url': agent.avatar_url,
                    'timezone': agent.timezone,
                    'language': agent.language
                } for agent in agents]
            })
        except Exception as e:
            logger.error(f"Failed to get agents: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/agents', methods=['POST'])
    def create_agent():
        """Create new agent"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No data provided'}), 400

            required_fields = ['username', 'email', 'first_name', 'last_name', 'password']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'{field} is required'}), 400

            # Check if username/email already exists
            if Agent.query.filter_by(username=data['username']).first():
                return jsonify({'success': False, 'message': 'Username already exists'}), 400
            if Agent.query.filter_by(email=data['email']).first():
                return jsonify({'success': False, 'message': 'Email already exists'}), 400

            agent = Agent(
                username=data['username'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                role=data.get('role', 'agent'),
                timezone=data.get('timezone', 'UTC'),
                language=data.get('language', 'en'),
                signature=data.get('signature'),
                avatar_url=data.get('avatar_url')
            )
            agent.set_password(data['password'])
            db.session.add(agent)
            db.session.commit()

            return jsonify({'success': True, 'agent_id': agent.id, 'message': 'Agent created successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create agent: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Ticket Assignment Endpoints
    @app.route('/api/ticket/<int:ticket_id>/assign', methods=['POST'])
    def assign_ticket(ticket_id):
        """Assign ticket to agent"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()

            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
                agent_id = data.get('agent_id') if data else None
            else:
                # Handle form data from HTMX select
                agent_id = request.form.get('assignee_id')
                if agent_id == '':  # Empty string from select option
                    agent_id = None
                elif agent_id:
                    agent_id = int(agent_id)

            # Store old assignee for activity logging
            old_assignee = ticket.assignee.full_name if ticket.assignee else None

            if agent_id:
                agent = Agent.query.get_or_404(agent_id)
                ticket.assign_to(agent)
                message = f'Ticket assigned to {agent.full_name}'

                # Log assignment activity
                TicketActivity.log_activity(
                    ticket_id=ticket_id,
                    activity_type='assignment',
                    description=message,
                    old_value=old_assignee,
                    new_value=agent.full_name,
                    is_public=True
                )
            else:
                ticket.assign_to(None)
                message = 'Ticket unassigned'

                # Log unassignment activity
                TicketActivity.log_activity(
                    ticket_id=ticket_id,
                    activity_type='assignment',
                    description=message,
                    old_value=old_assignee,
                    new_value=None,
                    is_public=True
                )

            db.session.commit()
            return jsonify({'success': True, 'message': message})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to assign ticket: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Enhanced Status Management
    @app.route('/api/ticket/<int:ticket_id>/status', methods=['POST'])
    def update_ticket_status(ticket_id):
        """Update ticket status with enhanced status values"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
                new_status = data.get('status') if data else None
            else:
                new_status = request.form.get('status')

            if not new_status:
                return jsonify({'success': False, 'message': 'Status is required'}), 400

            valid_statuses = ['new', 'open', 'pending', 'on-hold', 'solved', 'closed', 'archived']
            if new_status not in valid_statuses:
                return jsonify({'success': False, 'message': 'Invalid status'}), 400

            # Store old status for activity logging
            old_status = ticket.status

            ticket.set_status(new_status)

            # Log status change activity
            TicketActivity.log_activity(
                ticket_id=ticket_id,
                activity_type='status_change',
                description=f'Status changed from {old_status} to {new_status}',
                old_value=old_status,
                new_value=new_status,
                is_public=True
            )

            db.session.commit()

            return jsonify({'success': True, 'status': new_status, 'message': f'Ticket marked as {new_status}'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update ticket status: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/priority', methods=['POST'])
    def update_ticket_priority(ticket_id):
        """Update ticket priority"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()

            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
                new_priority = data.get('priority') if data else None
            else:
                new_priority = request.form.get('priority')

            if new_priority:
                new_priority = int(new_priority)

            if not new_priority or new_priority < 1 or new_priority > 5:
                return jsonify({'success': False, 'message': 'Priority must be 1-5'}), 400

            # Store old priority for activity logging
            old_priority = ticket.priority
            old_priority_label = ticket.get_priority_label()

            ticket.priority = new_priority
            ticket.updated_at = datetime.utcnow()

            # Log activity
            new_priority_label = ticket.get_priority_label()
            agent = Agent.query.first()  # TODO: Replace with proper session management
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=agent.id if agent else None,
                activity_type='priority_change',
                description=f'Priority changed from {old_priority_label} to {new_priority_label}',
                old_value=str(old_priority),
                new_value=str(new_priority)
            )

            db.session.commit()

            return jsonify({'success': True, 'priority': new_priority, 'message': f'Priority updated to {ticket.get_priority_label()}'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update ticket priority: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Tag Management Endpoints
    @app.route('/api/tags', methods=['GET'])
    def get_tags():
        """Get all active tags"""
        try:
            tags = Tag.query.filter_by(is_active=True).all()
            return jsonify({
                'success': True,
                'tags': [{
                    'id': tag.id,
                    'name': tag.name,
                    'description': tag.description,
                    'color': tag.color
                } for tag in tags]
            })
        except Exception as e:
            logger.error(f"Failed to get tags: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/tags', methods=['POST'])
    def create_tag():
        """Create new tag"""
        try:
            data = request.get_json()
            if not data or not data.get('name'):
                return jsonify({'success': False, 'message': 'Tag name is required'}), 400

            # Check if tag already exists
            if Tag.query.filter_by(name=data['name']).first():
                return jsonify({'success': False, 'message': 'Tag already exists'}), 400

            tag = Tag(
                name=data['name'],
                description=data.get('description'),
                color=data.get('color', '#3B82F6')
            )
            db.session.add(tag)
            db.session.commit()

            return jsonify({'success': True, 'tag_id': tag.id, 'message': 'Tag created successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create tag: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/tags', methods=['POST'])
    def add_ticket_tag(ticket_id):
        """Add tag to ticket"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            data = request.get_json()
            tag_id = data.get('tag_id')

            if not tag_id:
                return jsonify({'success': False, 'message': 'Tag ID is required'}), 400

            tag = Tag.query.get_or_404(tag_id)
            ticket.add_tag(tag)

            # Log activity
            agent = Agent.query.first()  # TODO: Replace with proper session management
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=agent.id if agent else None,
                activity_type='tag_added',
                description=f'Tag "{tag.name}" added',
                old_value=None,
                new_value=tag.name
            )

            db.session.commit()

            return jsonify({'success': True, 'message': f'Tag "{tag.name}" added to ticket'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add tag to ticket: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/tags/<int:tag_id>', methods=['DELETE'])
    def remove_ticket_tag(ticket_id, tag_id):
        """Remove tag from ticket"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            tag = Tag.query.get_or_404(tag_id)

            ticket.remove_tag(tag)

            # Log activity
            agent = Agent.query.first()  # TODO: Replace with proper session management
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=agent.id if agent else None,
                activity_type='tag_removed',
                description=f'Tag "{tag.name}" removed',
                old_value=tag.name,
                new_value=None
            )

            db.session.commit()

            return jsonify({'success': True, 'message': f'Tag "{tag.name}" removed from ticket'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to remove tag from ticket: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Reply System Endpoints
    @app.route('/api/ticket/<int:ticket_id>/replies', methods=['GET'])
    def get_ticket_replies(ticket_id):
        """Get all replies for a ticket"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            replies = ticket.replies.order_by(TicketReply.created_at.desc()).all()

            return jsonify({
                'success': True,
                'replies': [{
                    'id': reply.id,
                    'content': reply.content,
                    'content_html': reply.content_html,
                    'is_public': reply.is_public,
                    'is_system': reply.is_system,
                    'reply_type': reply.reply_type,
                    'agent': {
                        'id': reply.agent.id,
                        'full_name': reply.agent.full_name,
                        'avatar_url': reply.agent.avatar_url
                    } if reply.agent else None,
                    'created_at': reply.created_at.isoformat(),
                    'relative_time': reply.get_relative_time(),
                    'attachments': [{
                        'id': att.id,
                        'filename': att.filename,
                        'size': att.size,
                        'content_type': att.content_type
                    } for att in reply.attachments]
                } for reply in replies]
            })
        except Exception as e:
            logger.error(f"Failed to get ticket replies: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/replies', methods=['POST'])
    def add_reply(ticket_id):
        """Add reply to ticket"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            data = request.get_json() if request.is_json else request.form.to_dict()

            if not data or not data.get('content'):
                return jsonify({'success': False, 'message': 'Reply content is required'}), 400

            # For now, use first agent as default (in real app, get from session)
            agent = Agent.query.first()
            if not agent:
                return jsonify({'success': False, 'message': 'No agents available'}), 400

            reply = TicketReply(
                ticket_id=ticket_id,
                agent_id=agent.id,
                content=data['content'],
                is_public=data.get('reply_type', 'public') == 'public',
                reply_type=data.get('reply_type', 'reply')
            )
            db.session.add(reply)

            # Update ticket status if requested
            new_status = data.get('new_status')
            if new_status and new_status != ticket.status:
                ticket.set_status(new_status)

            # Set first reply timestamp if this is the first agent response
            if not ticket.first_reply_at and reply.is_public:
                ticket.first_reply_at = datetime.utcnow()

            # Log activity
            reply_type_label = 'Public Reply' if reply.is_public else 'Internal Note'
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=agent.id,
                activity_type='reply_added',
                description=f'{reply_type_label} added',
                new_value=reply_type_label,
                is_public=reply.is_public
            )

            ticket.updated_at = datetime.utcnow()
            db.session.commit()

            return jsonify({'success': True, 'reply_id': reply.id, 'message': 'Reply added successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add reply: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/attachment/reply/<int:attachment_id>')
    def download_reply_attachment(attachment_id):
        """Download reply attachment"""
        try:
            attachment = ReplyAttachment.query.get_or_404(attachment_id)
            return send_file(
                attachment.storage_path,
                as_attachment=True,
                download_name=attachment.filename,
                mimetype=attachment.content_type
            )
        except FileNotFoundError:
            logger.error(f"Reply attachment file not found: {attachment.storage_path}")
            return jsonify({'error': 'File not found'}), 404
        except Exception as e:
            logger.error(f"Failed to download reply attachment: {str(e)}")
            return jsonify({'error': 'Download failed'}), 500

    # Follower Management Endpoints
    @app.route('/api/ticket/<int:ticket_id>/followers', methods=['GET'])
    def get_ticket_followers(ticket_id):
        """Get ticket followers"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            followers = ticket.get_followers_list()

            return jsonify({
                'success': True,
                'followers': [{
                    'id': follower.id,
                    'full_name': follower.full_name,
                    'email': follower.email,
                    'avatar_url': follower.avatar_url
                } for follower in followers]
            })
        except Exception as e:
            logger.error(f"Failed to get ticket followers: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/followers', methods=['POST'])
    def add_ticket_follower(ticket_id):
        """Add follower to ticket"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            data = request.get_json()
            agent_id = data.get('agent_id')

            if not agent_id:
                return jsonify({'success': False, 'message': 'Agent ID is required'}), 400

            agent = Agent.query.get_or_404(agent_id)
            ticket.add_follower(agent)

            # Log activity
            current_agent = Agent.query.first()  # TODO: Replace with proper session management
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=current_agent.id if current_agent else None,
                activity_type='follower_added',
                description=f'{agent.full_name} added as follower',
                old_value=None,
                new_value=agent.full_name
            )

            db.session.commit()

            return jsonify({'success': True, 'message': f'{agent.full_name} is now following this ticket'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add ticket follower: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/followers/<int:agent_id>', methods=['DELETE'])
    def remove_ticket_follower(ticket_id, agent_id):
        """Remove follower from ticket"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            agent = Agent.query.get_or_404(agent_id)

            ticket.remove_follower(agent)

            # Log activity
            current_agent = Agent.query.first()  # TODO: Replace with proper session management
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=current_agent.id if current_agent else None,
                activity_type='follower_removed',
                description=f'{agent.full_name} removed as follower',
                old_value=agent.full_name,
                new_value=None
            )

            db.session.commit()

            return jsonify({'success': True, 'message': f'{agent.full_name} is no longer following this ticket'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to remove ticket follower: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Organization Management Endpoints
    @app.route('/api/organizations', methods=['GET'])
    def get_organizations():
        """Get all active organizations"""
        try:
            organizations = Organization.query.filter_by(is_active=True).all()
            return jsonify({
                'success': True,
                'organizations': [{
                    'id': org.id,
                    'name': org.name,
                    'domain': org.domain,
                    'description': org.description,
                    'website': org.website,
                    'industry': org.industry,
                    'size': org.size
                } for org in organizations]
            })
        except Exception as e:
            logger.error(f"Failed to get organizations: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/organizations', methods=['POST'])
    def create_organization():
        """Create new organization"""
        try:
            data = request.get_json()
            if not data or not data.get('name'):
                return jsonify({'success': False, 'message': 'Organization name is required'}), 400

            organization = Organization(
                name=data['name'],
                domain=data.get('domain'),
                description=data.get('description'),
                website=data.get('website'),
                industry=data.get('industry'),
                size=data.get('size')
            )
            db.session.add(organization)
            db.session.commit()

            return jsonify({'success': True, 'organization_id': organization.id, 'message': 'Organization created successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create organization: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Ticket Type Management Endpoints
    @app.route('/api/ticket-types', methods=['GET'])
    def get_ticket_types():
        """Get all active ticket types"""
        try:
            ticket_types = TicketType.query.filter_by(is_active=True).order_by(TicketType.sort_order).all()
            return jsonify({
                'success': True,
                'ticket_types': [{
                    'id': tt.id,
                    'name': tt.name,
                    'description': tt.description,
                    'color': tt.color,
                    'icon': tt.icon,
                    'default_priority': tt.default_priority
                } for tt in ticket_types]
            })
        except Exception as e:
            logger.error(f"Failed to get ticket types: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket-types', methods=['POST'])
    def create_ticket_type():
        """Create new ticket type"""
        try:
            data = request.get_json()
            if not data or not data.get('name'):
                return jsonify({'success': False, 'message': 'Ticket type name is required'}), 400

            ticket_type = TicketType(
                name=data['name'],
                description=data.get('description'),
                color=data.get('color', '#6B7280'),
                icon=data.get('icon'),
                default_priority=data.get('default_priority', 3)
            )
            db.session.add(ticket_type)
            db.session.commit()

            return jsonify({'success': True, 'ticket_type_id': ticket_type.id, 'message': 'Ticket type created successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create ticket type: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Master Data CRUD - UPDATE and DELETE Operations

    # Agent Management - UPDATE and DELETE
    @app.route('/api/agents/<int:agent_id>', methods=['PUT'])
    def update_agent(agent_id):
        """Update agent"""
        try:
            agent = Agent.query.get_or_404(agent_id)
            data = request.get_json()

            agent.username = data.get('username', agent.username)
            agent.email = data.get('email', agent.email)
            agent.first_name = data.get('first_name', agent.first_name)
            agent.last_name = data.get('last_name', agent.last_name)
            agent.role = data.get('role', agent.role)
            agent.timezone = data.get('timezone', agent.timezone)
            agent.signature = data.get('signature', agent.signature)
            agent.is_active = data.get('is_active', agent.is_active)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Agent updated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update agent: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/agents/<int:agent_id>', methods=['DELETE'])
    def delete_agent(agent_id):
        """Delete (deactivate) agent"""
        try:
            agent = Agent.query.get_or_404(agent_id)
            agent.is_active = False
            db.session.commit()
            return jsonify({'success': True, 'message': 'Agent deactivated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete agent: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Organization Management - UPDATE and DELETE
    @app.route('/api/organizations/<int:org_id>', methods=['PUT'])
    def update_organization(org_id):
        """Update organization"""
        try:
            organization = Organization.query.get_or_404(org_id)
            data = request.get_json()

            organization.name = data.get('name', organization.name)
            organization.domain = data.get('domain', organization.domain)
            organization.description = data.get('description', organization.description)
            organization.website = data.get('website', organization.website)
            organization.industry = data.get('industry', organization.industry)
            organization.size = data.get('size', organization.size)
            organization.is_active = data.get('is_active', organization.is_active)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Organization updated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update organization: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/organizations/<int:org_id>', methods=['DELETE'])
    def delete_organization(org_id):
        """Delete (deactivate) organization"""
        try:
            organization = Organization.query.get_or_404(org_id)
            organization.is_active = False
            db.session.commit()
            return jsonify({'success': True, 'message': 'Organization deactivated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete organization: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Ticket Type Management - UPDATE and DELETE
    @app.route('/api/ticket-types/<int:type_id>', methods=['PUT'])
    def update_ticket_type(type_id):
        """Update ticket type"""
        try:
            ticket_type = TicketType.query.get_or_404(type_id)
            data = request.get_json()

            ticket_type.name = data.get('name', ticket_type.name)
            ticket_type.description = data.get('description', ticket_type.description)
            ticket_type.color = data.get('color', ticket_type.color)
            ticket_type.icon = data.get('icon', ticket_type.icon)
            ticket_type.default_priority = data.get('default_priority', ticket_type.default_priority)
            ticket_type.sort_order = data.get('sort_order', ticket_type.sort_order)
            ticket_type.is_active = data.get('is_active', ticket_type.is_active)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Ticket type updated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update ticket type: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket-types/<int:type_id>', methods=['DELETE'])
    def delete_ticket_type(type_id):
        """Delete (deactivate) ticket type"""
        try:
            ticket_type = TicketType.query.get_or_404(type_id)
            ticket_type.is_active = False
            db.session.commit()
            return jsonify({'success': True, 'message': 'Ticket type deactivated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete ticket type: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Tag Management - UPDATE and DELETE
    @app.route('/api/tags/<int:tag_id>', methods=['PUT'])
    def update_tag(tag_id):
        """Update tag"""
        try:
            tag = Tag.query.get_or_404(tag_id)
            data = request.get_json()

            tag.name = data.get('name', tag.name)
            tag.description = data.get('description', tag.description)
            tag.color = data.get('color', tag.color)
            tag.is_active = data.get('is_active', tag.is_active)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Tag updated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update tag: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
    def delete_tag(tag_id):
        """Delete (deactivate) tag"""
        try:
            tag = Tag.query.get_or_404(tag_id)
            tag.is_active = False
            db.session.commit()
            return jsonify({'success': True, 'message': 'Tag deactivated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete tag: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Status Management Endpoints
    @app.route('/api/statuses', methods=['GET'])
    def get_statuses():
        """Get all active statuses"""
        try:
            statuses = Status.query.filter_by(is_active=True).order_by(Status.display_order).all()
            return jsonify({
                'success': True,
                'statuses': [{
                    'id': status.id,
                    'name': status.name,
                    'description': status.description,
                    'color': status.color,
                    'is_closed_status': status.is_closed_status,
                    'display_order': status.display_order
                } for status in statuses]
            })
        except Exception as e:
            logger.error(f"Failed to get statuses: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/statuses', methods=['POST'])
    def create_status():
        """Create new status"""
        try:
            data = request.get_json()
            if not data or not data.get('name'):
                return jsonify({'success': False, 'message': 'Status name is required'}), 400

            # Check if status already exists
            if Status.query.filter_by(name=data['name']).first():
                return jsonify({'success': False, 'message': 'Status already exists'}), 400

            status = Status(
                name=data['name'],
                description=data.get('description'),
                color=data.get('color', '#6B7280'),
                is_closed_status=data.get('is_closed_status', False),
                display_order=data.get('display_order', 0)
            )
            db.session.add(status)
            db.session.commit()

            return jsonify({'success': True, 'status_id': status.id, 'message': 'Status created successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create status: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/statuses/<int:status_id>', methods=['PUT'])
    def update_status(status_id):
        """Update status"""
        try:
            status = Status.query.get_or_404(status_id)
            data = request.get_json()

            status.name = data.get('name', status.name)
            status.description = data.get('description', status.description)
            status.color = data.get('color', status.color)
            status.is_closed_status = data.get('is_closed_status', status.is_closed_status)
            status.display_order = data.get('display_order', status.display_order)
            status.is_active = data.get('is_active', status.is_active)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Status updated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update status: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/statuses/<int:status_id>', methods=['DELETE'])
    def delete_status(status_id):
        """Delete (deactivate) status"""
        try:
            status = Status.query.get_or_404(status_id)
            status.is_active = False
            db.session.commit()
            return jsonify({'success': True, 'message': 'Status deactivated successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete status: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # API endpoint for filter options
    @app.route('/api/filter-options', methods=['GET'])
    def get_filter_options():
        """Get all available filter options for tickets"""
        try:
            agents = Agent.query.filter_by(is_active=True).all()
            organizations = Organization.query.all()
            ticket_types = TicketType.query.filter_by(is_active=True).all()
            tags = Tag.query.filter_by(is_active=True).all()

            return jsonify({
                'success': True,
                'agents': [{'id': a.id, 'name': a.full_name} for a in agents],
                'organizations': [{'id': o.id, 'name': o.name} for o in organizations],
                'ticket_types': [{'id': t.id, 'name': t.name, 'color': t.color} for t in ticket_types],
                'tags': [{'id': t.id, 'name': t.name, 'color': t.color} for t in tags]
            })
        except Exception as e:
            logger.error(f"Failed to get filter options: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Saved Filters API
    @app.route('/api/saved-filters', methods=['GET'])
    def get_saved_filters():
        """Get all saved filters for the current agent"""
        try:
            # TODO: Get current agent ID from session (for now using first agent)
            agent = Agent.query.first()
            if not agent:
                return jsonify({'success': False, 'message': 'No agent found'}), 404

            # Get filters owned by agent or shared filters
            filters = SavedFilter.query.filter(
                db.or_(
                    SavedFilter.agent_id == agent.id,
                    SavedFilter.is_shared == True
                )
            ).order_by(SavedFilter.sort_order, SavedFilter.created_at.desc()).all()

            return jsonify({
                'success': True,
                'filters': [f.to_dict() for f in filters]
            })
        except Exception as e:
            logger.error(f"Failed to get saved filters: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/saved-filters', methods=['POST'])
    def create_saved_filter():
        """Create a new saved filter"""
        try:
            data = request.get_json()

            # Validate required fields
            if not data.get('name'):
                return jsonify({'success': False, 'message': 'Filter name is required'}), 400

            if not data.get('criteria'):
                return jsonify({'success': False, 'message': 'Filter criteria is required'}), 400

            # TODO: Get current agent ID from session (for now using first agent)
            agent = Agent.query.first()
            if not agent:
                return jsonify({'success': False, 'message': 'No agent found'}), 404

            # If setting as default, unset other default filters for this agent
            if data.get('is_default'):
                SavedFilter.query.filter_by(agent_id=agent.id, is_default=True).update({'is_default': False})

            # Create new saved filter
            saved_filter = SavedFilter(
                name=data['name'],
                description=data.get('description', ''),
                agent_id=agent.id,
                is_default=data.get('is_default', False),
                is_favorite=data.get('is_favorite', False),
                is_shared=data.get('is_shared', False),
                sort_order=data.get('sort_order', 0)
            )
            saved_filter.set_criteria(data['criteria'])

            db.session.add(saved_filter)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Filter saved successfully',
                'filter': saved_filter.to_dict()
            })
        except Exception as e:
            logger.error(f"Failed to create saved filter: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/saved-filters/<int:filter_id>', methods=['PUT'])
    def update_saved_filter(filter_id):
        """Update an existing saved filter"""
        try:
            saved_filter = SavedFilter.query.get_or_404(filter_id)

            # TODO: Check if agent owns this filter
            data = request.get_json()

            # Update fields
            if 'name' in data:
                saved_filter.name = data['name']
            if 'description' in data:
                saved_filter.description = data['description']
            if 'criteria' in data:
                saved_filter.set_criteria(data['criteria'])
            if 'is_favorite' in data:
                saved_filter.is_favorite = data['is_favorite']
            if 'is_shared' in data:
                saved_filter.is_shared = data['is_shared']
            if 'sort_order' in data:
                saved_filter.sort_order = data['sort_order']

            # Handle default filter
            if 'is_default' in data and data['is_default']:
                # Unset other default filters for this agent
                SavedFilter.query.filter_by(agent_id=saved_filter.agent_id, is_default=True).update({'is_default': False})
                saved_filter.is_default = True
            elif 'is_default' in data:
                saved_filter.is_default = False

            saved_filter.updated_at = datetime.utcnow()
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Filter updated successfully',
                'filter': saved_filter.to_dict()
            })
        except Exception as e:
            logger.error(f"Failed to update saved filter: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/saved-filters/<int:filter_id>', methods=['DELETE'])
    def delete_saved_filter(filter_id):
        """Delete a saved filter"""
        try:
            saved_filter = SavedFilter.query.get_or_404(filter_id)

            # TODO: Check if agent owns this filter

            db.session.delete(saved_filter)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Filter deleted successfully'
            })
        except Exception as e:
            logger.error(f"Failed to delete saved filter: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    # Enhanced Search and Filtering
    @app.route('/api/tickets/search', methods=['GET'])
    def search_tickets():
        """Advanced ticket search with comprehensive filtering"""
        try:
            query = Ticket.query.filter(Ticket.is_deleted == False)

            # Basic filters
            status = request.args.get('status')
            if status and status != 'all':
                query = query.filter_by(status=status)

            # Multi-select filters
            assignee_ids = request.args.getlist('assignee_ids')
            if assignee_ids:
                # Handle 'unassigned' option
                if 'unassigned' in assignee_ids:
                    # Include both unassigned and any other selected assignees
                    other_ids = [id for id in assignee_ids if id != 'unassigned']
                    if other_ids:
                        query = query.filter(db.or_(
                            Ticket.assignee_id == None,
                            Ticket.assignee_id.in_(other_ids)
                        ))
                    else:
                        query = query.filter(Ticket.assignee_id == None)
                else:
                    query = query.filter(Ticket.assignee_id.in_(assignee_ids))

            organization_ids = request.args.getlist('organization_ids')
            if organization_ids:
                query = query.filter(Ticket.organization_id.in_(organization_ids))

            type_ids = request.args.getlist('type_ids')
            if type_ids:
                query = query.filter(Ticket.type_id.in_(type_ids))

            priorities = request.args.getlist('priorities')
            if priorities:
                query = query.filter(Ticket.priority.in_(priorities))

            # Text search
            search = request.args.get('search')
            if search:
                query = query.filter(
                    db.or_(
                        Ticket.subject.contains(search),
                        Ticket.sender_name.contains(search),
                        Ticket.sender_email.contains(search),
                        Ticket.content_text.contains(search)
                    )
                )

            # Tag filter - multi-select
            tag_ids = request.args.getlist('tag_ids')
            if tag_ids:
                query = query.join(Ticket.tags).filter(Tag.id.in_(tag_ids))

            # Date range
            date_from = request.args.get('date_from')
            date_to = request.args.get('date_to')
            if date_from:
                query = query.filter(Ticket.created_at >= date_from)
            if date_to:
                query = query.filter(Ticket.created_at <= date_to)

            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)

            tickets = query.order_by(Ticket.received_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )

            return jsonify({
                'success': True,
                'tickets': [{
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'status_label': ticket.get_status_label(),
                    'priority': ticket.priority,
                    'type_id': ticket.type_id,
                    'is_read': ticket.is_read,
                    'sender_name': ticket.sender_name,
                    'sender_email': ticket.sender_email,
                    'assignee': {
                        'id': ticket.assignee.id,
                        'full_name': ticket.assignee.full_name
                    } if ticket.assignee else None,
                    'organization': {
                        'id': ticket.organization.id,
                        'name': ticket.organization.name
                    } if ticket.organization else None,
                    'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
                    'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
                    'tags': [{'id': tag.id, 'name': tag.name, 'color': tag.color} for tag in ticket.tags]
                } for ticket in tickets.items],
                'pagination': {
                    'page': tickets.page,
                    'pages': tickets.pages,
                    'per_page': tickets.per_page,
                    'total': tickets.total,
                    'has_next': tickets.has_next,
                    'has_prev': tickets.has_prev
                }
            })
        except Exception as e:
            logger.error(f"Failed to search tickets: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/tickets/create', methods=['POST'])
    def create_ticket_manually():
        """Create ticket manually by agents"""
        try:
            # Handle both JSON and form data
            content_type = request.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                data = request.get_json()
            else:
                data = request.form.to_dict()

            if not data:
                return jsonify({'success': False, 'message': 'No data provided'}), 400

            # Validate required fields
            required_fields = ['subject', 'sender_email', 'content_text']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'{field.replace("_", " ").title()} is required'}), 400

            # Sanitize inputs
            for field in ['subject', 'sender_email', 'content_text', 'sender_name', 'recipient_email', 'cc_emails', 'internal_notes']:
                if data.get(field):
                    data[field] = sanitize_input(data[field])

            # Validate email format
            import re
            from werkzeug.utils import secure_filename
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, data['sender_email']):
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400

            # Helper function to safely convert to int
            def safe_int(value):
                if value is None:
                    return None
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.strip():
                    try:
                        return int(value.strip())
                    except ValueError:
                        return None
                return None

            # Create ticket
            ticket = Ticket(
                ticket_number=Ticket.create_unique_ticket_number(),
                source='manual',
                source_id=f"manual-{datetime.utcnow().isoformat()}",
                channel='agent',
                subject=data['subject'],
                content_text=data['content_text'],
                content_html=data.get('content_html'),
                sender_email=data['sender_email'],
                sender_name=data.get('sender_name', ''),
                recipient_email=data.get('recipient_email', ''),
                assignee_id=safe_int(data.get('assignee_id')),
                organization_id=safe_int(data.get('organization_id')),
                type_id=safe_int(data.get('type_id')),
                priority=int(data.get('priority', 3)),
                urgency=int(data.get('urgency', 3)),
                status='new',
                received_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )

            # Set CC emails if provided
            if data.get('cc_emails'):
                if isinstance(data['cc_emails'], list):
                    ticket.set_cc_emails(data['cc_emails'])
                else:
                    # Split comma-separated emails
                    cc_list = [email.strip() for email in data['cc_emails'].split(',') if email.strip()]
                    ticket.set_cc_emails(cc_list)

            # Set internal notes if provided
            if data.get('internal_notes'):
                ticket.internal_notes = data['internal_notes']

            # Save ticket first to get ID
            db.session.add(ticket)
            db.session.flush()  # Get the ID

            # Handle file attachments
            if 'attachments' in request.files:
                attachments = request.files.getlist('attachments')
                for attachment_file in attachments:
                    if attachment_file and attachment_file.filename and attachment_file.filename.strip():
                        try:
                            # Validate file size (5MB limit for manual tickets)
                            attachment_file.seek(0, 2)  # Seek to end
                            file_size = attachment_file.tell()  # Get size
                            attachment_file.seek(0)  # Reset

                            if file_size > 5 * 1024 * 1024:  # 5MB limit
                                logger.warning(f"Attachment {attachment_file.filename} too large ({file_size} bytes)")
                                continue

                            if file_size == 0:
                                logger.warning(f"Attachment {attachment_file.filename} is empty")
                                continue

                            # Create filename
                            filename = secure_filename(attachment_file.filename)
                            if not filename:
                                logger.warning(f"Invalid filename: {attachment_file.filename}")
                                continue

                            # Generate unique filename for storage
                            import uuid
                            file_ext = os.path.splitext(filename)[1]
                            unique_filename = f"{uuid.uuid4().hex}{file_ext}"

                            # Get upload path
                            upload_path = os.path.join(app.config.get('UPLOAD_FOLDER', 'uploads'), unique_filename)

                            # Ensure directory exists
                            os.makedirs(os.path.dirname(upload_path), exist_ok=True)

                            # Save file to disk
                            attachment_file.save(upload_path)

                            # Create attachment record
                            attachment = Attachment(
                                ticket_id=ticket.id,
                                filename=filename,
                                content_type=attachment_file.content_type or 'application/octet-stream',
                                size=file_size,
                                storage_path=upload_path,
                                created_at=datetime.utcnow()
                            )
                            db.session.add(attachment)
                            logger.info(f"Saved attachment {filename} ({file_size} bytes) for manual ticket {ticket.ticket_number}")

                        except Exception as e:
                            logger.error(f"Failed to save attachment {attachment_file.filename}: {str(e)}")
                            continue

            # Add tags if provided
            if data.get('tag_ids'):
                tag_ids = data['tag_ids']
                if isinstance(tag_ids, str):
                    tag_ids = [int(x.strip()) for x in tag_ids.split(',') if x.strip().isdigit()]
                elif isinstance(tag_ids, list):
                    tag_ids = [int(x) for x in tag_ids if str(x).isdigit()]

                for tag_id in tag_ids:
                    tag = Tag.query.get(tag_id)
                    if tag:
                        ticket.tags.append(tag)

            # Log activity
            current_agent = Agent.query.first()  # TODO: Replace with proper session management
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=current_agent.id if current_agent else None,
                activity_type='ticket_created',
                description=f'Ticket created manually by {current_agent.full_name if current_agent else "Unknown"}',
                old_value=None,
                new_value='Manual Creation'
            )

            db.session.commit()

            return jsonify({
                'success': True,
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'message': 'Ticket created successfully'
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create ticket manually: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/widget/submit', methods=['POST', 'OPTIONS'])
    def widget_submit():
        """Handle widget form submissions from external websites"""

        # Handle preflight OPTIONS request
        if request.method == 'OPTIONS':
            response = jsonify({'status': 'ok'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
            return response

        try:
            # Rate limiting check
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
            if client_ip and is_rate_limited(client_ip):
                response = jsonify({'success': False, 'message': 'Too many requests. Please try again later.'})
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 429

            # Handle both JSON and multipart form data
            attachment_file = None
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                # Handle form data with potential file upload
                data = request.form.to_dict()
                if 'attachment' in request.files:
                    attachment_file = request.files['attachment']
                    # Check if file has content
                    if attachment_file.filename and attachment_file.filename.strip():
                        # Read content to check file size (1MB limit)
                        attachment_file.seek(0, 2)  # Seek to end of file
                        file_size = attachment_file.tell()  # Get file size
                        attachment_file.seek(0)  # Reset to beginning

                        if file_size > 1024 * 1024:  # 1MB limit
                            response = jsonify({'success': False, 'message': 'File size must be less than 1MB'})
                            response.headers.add('Access-Control-Allow-Origin', '*')
                            return response, 400
            else:
                # Handle JSON data
                data = request.get_json()

            if not data:
                response = jsonify({'success': False, 'message': 'No data provided'})
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 400

            # Basic validation
            required_fields = ['email', 'message']
            for field in required_fields:
                if not data.get(field):
                    response = jsonify({'success': False, 'message': f'{field.replace("_", " ").title()} is required'})
                    response.headers.add('Access-Control-Allow-Origin', '*')
                    return response, 400

            # Sanitize inputs
            data['email'] = sanitize_input(data['email'])
            data['message'] = sanitize_input(data['message'])
            if data.get('name'):
                data['name'] = sanitize_input(data['name'])
            if data.get('subject'):
                data['subject'] = sanitize_input(data['subject'])

            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, data['email']):
                response = jsonify({'success': False, 'message': 'Invalid email format'})
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 400

            # Create ticket from widget submission
            ticket = Ticket(
                ticket_number=Ticket.create_unique_ticket_number(),
                source='widget',
                source_id=f"widget-{datetime.utcnow().isoformat()}",
                channel='web',
                subject=data.get('subject', 'Support Request from Website'),
                content_text=data['message'],
                sender_email=data['email'],
                sender_name=data.get('name', ''),
                status='new',
                priority=3,  # Normal priority for widget submissions
                received_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )

            # Save ticket
            db.session.add(ticket)
            db.session.flush()

            # Handle file attachment if present
            if attachment_file and attachment_file.filename:
                try:
                    # Save attachment using existing attachment handling
                    import uuid
                    from werkzeug.utils import secure_filename
                    import os

                    # Generate unique filename
                    file_ext = os.path.splitext(secure_filename(attachment_file.filename))[1]
                    unique_filename = f"{uuid.uuid4().hex}{file_ext}"

                    # Get upload path
                    upload_path = os.path.join(app.config.get('UPLOAD_FOLDER', 'uploads'), unique_filename)

                    # Ensure directory exists
                    os.makedirs(os.path.dirname(upload_path), exist_ok=True)

                    # Save file
                    attachment_file.save(upload_path)

                    # Create attachment record
                    from database.models import Attachment
                    attachment = Attachment(
                        ticket_id=ticket.id,
                        filename=secure_filename(attachment_file.filename),
                        storage_path=upload_path,
                        size=os.path.getsize(upload_path),
                        content_type=attachment_file.content_type or 'application/octet-stream',
                        created_at=datetime.utcnow()
                    )
                    db.session.add(attachment)

                except Exception as e:
                    logger.error(f"Failed to save widget attachment: {str(e)}")
                    # Don't fail the ticket creation if attachment fails

            # Log activity
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=None,
                activity_type='ticket_created',
                description='Ticket created via website widget',
                old_value=None,
                new_value='Widget Submission'
            )

            db.session.commit()

            response = jsonify({
                'success': True,
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'message': 'Your message has been received. We\'ll get back to you soon!'
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create ticket from widget: {str(e)}")
            response = jsonify({'success': False, 'message': 'Failed to submit message. Please try again.'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 500

    @app.route('/widget')
    def widget_iframe():
        """Serve widget as standalone iframe page"""
        return render_template('widget_iframe.html')

    @app.route('/widget-simulate')
    def widget_simulate():
        """Serve widget simulation test page"""
        # Ensure we have the correct API URL
        api_url = request.url_root.rstrip('/')
        return render_template('widget_simulate.html', api_url=api_url)

    @app.route('/api/ticket/<int:ticket_id>/type', methods=['POST'])
    def update_ticket_type_assignment(ticket_id):
        """Update ticket type"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()

            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
                type_id = data.get('type_id') if data else None
            else:
                type_id = request.form.get('type_id')

            if type_id:
                ticket_type = TicketType.query.get(type_id)
                if ticket_type and ticket_type.is_active:
                    # Store old type for activity logging
                    old_type = ticket.ticket_type.name if ticket.ticket_type else 'None'

                    ticket.type_id = ticket_type.id
                    ticket.updated_at = datetime.utcnow()

                    # Log activity
                    agent = Agent.query.first()  # TODO: Replace with proper session management
                    TicketActivity.log_activity(
                        ticket_id=ticket.id,
                        agent_id=agent.id if agent else None,
                        activity_type='type_change',
                        description=f'Type changed from {old_type} to {ticket_type.name}',
                        old_value=old_type,
                        new_value=ticket_type.name
                    )

                    db.session.commit()
                    return jsonify({'success': True})
            else:
                # Handle clearing the type (setting to None)
                old_type = ticket.ticket_type.name if ticket.ticket_type else 'None'
                ticket.type_id = None
                ticket.updated_at = datetime.utcnow()

                # Log activity
                agent = Agent.query.first()  # TODO: Replace with proper session management
                TicketActivity.log_activity(
                    ticket_id=ticket.id,
                    agent_id=agent.id if agent else None,
                    activity_type='type_change',
                    description=f'Type changed from {old_type} to None',
                    old_value=old_type,
                    new_value='None'
                )

                db.session.commit()
                return jsonify({'success': True})

            return jsonify({'success': False, 'message': 'Invalid ticket type'}), 400
        except Exception as e:
            logger.error(f"Failed to update ticket type: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/topic', methods=['POST'])
    def update_ticket_topic(ticket_id):
        """Update ticket topic/category"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()

            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
                topic_content = data.get('topic', '') if data else ''
            else:
                topic_content = request.form.get('topic', '')

            # Store old topic for activity logging
            old_topic = ticket.topic or 'None'

            ticket.topic = topic_content
            ticket.updated_at = datetime.utcnow()

            # Log activity
            new_topic = topic_content or 'None'
            agent = Agent.query.first()  # TODO: Replace with proper session management
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=agent.id if agent else None,
                activity_type='topic_change',
                description=f'Topic changed from "{old_topic}" to "{new_topic}"',
                old_value=old_topic,
                new_value=new_topic
            )

            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Failed to update ticket topic: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/subject', methods=['POST'])
    def update_ticket_subject(ticket_id):
        """Update ticket subject"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            data = request.get_json()

            if not data:
                return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400

            if 'subject' in data and data['subject'].strip():
                ticket.subject = data['subject'].strip()
                ticket.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'success': True})

            return jsonify({'success': False, 'message': 'Subject cannot be empty'}), 400
        except Exception as e:
            logger.error(f"Failed to update ticket subject: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/notes', methods=['POST'])
    def update_ticket_notes(ticket_id):
        """Update ticket internal notes"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()

            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
                notes_content = data.get('notes', '') if data else ''
            else:
                notes_content = request.form.get('notes', '')

            # Store old notes for activity logging
            old_notes = ticket.notes or ''

            ticket.notes = notes_content
            ticket.updated_at = datetime.utcnow()

            # Log activity (internal note changes are private)
            agent = Agent.query.first()  # TODO: Replace with proper session management
            TicketActivity.log_activity(
                ticket_id=ticket.id,
                agent_id=agent.id if agent else None,
                activity_type='notes_updated',
                description='Agent notes updated',
                old_value=old_notes,
                new_value=notes_content,
                is_public=False  # Notes are internal only
            )

            db.session.commit()
            return jsonify({'success': True})

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update ticket notes: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ticket/<int:ticket_id>/activities', methods=['GET'])
    def get_ticket_activities(ticket_id):
        """Get ticket activity timeline"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            activities = ticket.activities.order_by(TicketActivity.created_at.desc()).all()

            # Add ticket creation as first activity if no activities exist
            activity_list = []

            # Add ticket creation
            activity_list.append({
                'type': 'ticket_created',
                'description': f'Ticket created by {ticket.sender_name or "Customer"}',
                'agent_name': ticket.sender_name or 'Customer',
                'created_at': ticket.created_at,
                'icon': 'create',
                'color': 'green'
            })

            # Add all logged activities
            for activity in activities:
                activity_list.append({
                    'type': activity.activity_type,
                    'description': activity.description,
                    'agent_name': activity.agent.full_name if activity.agent else 'System',
                    'created_at': activity.created_at,
                    'old_value': activity.old_value,
                    'new_value': activity.new_value,
                    'is_public': activity.is_public,
                    'icon': get_activity_icon(activity.activity_type),
                    'color': get_activity_color(activity.activity_type)
                })

            return render_template('components/activity_timeline.html', activities=activity_list)
        except Exception as e:
            logger.error(f"Failed to get ticket activities: {str(e)}")
            return '<div class="text-center py-4 text-red-500">Failed to load timeline</div>'

    def get_activity_icon(activity_type):
        """Get icon for activity type"""
        icons = {
            'status_change': 'status',
            'assignment_change': 'user',
            'priority_change': 'priority',
            'type_change': 'type',
            'topic_change': 'edit',
            'reply_added': 'reply',
            'tag_added': 'tag-add',
            'tag_removed': 'tag-remove',
            'follower_added': 'user-add',
            'follower_removed': 'user-remove',
            'notes_updated': 'note',
            'ticket_created': 'create'
        }
        return icons.get(activity_type, 'activity')

    def get_activity_color(activity_type):
        """Get color for activity type"""
        colors = {
            'status_change': 'blue',
            'assignment_change': 'purple',
            'priority_change': 'orange',
            'type_change': 'indigo',
            'topic_change': 'gray',
            'reply_added': 'green',
            'tag_added': 'pink',
            'tag_removed': 'red',
            'follower_added': 'teal',
            'follower_removed': 'red',
            'notes_updated': 'yellow',
            'ticket_created': 'green'
        }
        return colors.get(activity_type, 'gray')

    # Ticket Relationship Endpoints (Merge, Split, Link)
    @app.route('/api/ticket/<int:ticket_id>/merge', methods=['POST'])
    def merge_ticket(ticket_id):
        """Merge ticket into another ticket"""
        try:
            source_ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()

            data = request.get_json()
            target_ticket_id = data.get('target_ticket_id')
            merge_replies = data.get('merge_replies', True)
            merge_tags = data.get('merge_tags', True)
            close_source = data.get('close_source', True)
            agent_id = data.get('agent_id')

            if not target_ticket_id:
                return jsonify({'success': False, 'message': 'Target ticket ID required'}), 400

            target_ticket = Ticket.query.filter(Ticket.id == target_ticket_id, Ticket.is_deleted == False).first()
            if not target_ticket:
                return jsonify({'success': False, 'message': 'Target ticket not found'}), 404

            if not source_ticket.can_merge():
                return jsonify({'success': False, 'message': 'Source ticket cannot be merged'}), 400

            # Perform merge
            relationship = source_ticket.merge_into(
                target_ticket,
                agent_id=agent_id,
                merge_replies=merge_replies,
                merge_tags=merge_tags,
                close_source=close_source
            )

            return jsonify({
                'success': True,
                'message': f'Ticket {source_ticket.ticket_number} merged into {target_ticket.ticket_number}',
                'source_ticket_id': source_ticket.id,
                'target_ticket_id': target_ticket.id,
                'relationship_id': relationship.id
            })

        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error merging ticket: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error merging ticket: {str(e)}'}), 500

    @app.route('/api/ticket/<int:ticket_id>/split', methods=['POST'])
    def split_ticket(ticket_id):
        """Split ticket into multiple child tickets"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()

            data = request.get_json()
            num_tickets = data.get('num_tickets', 2)
            assignees = data.get('assignees', [])
            split_criteria = data.get('split_criteria')
            agent_id = data.get('agent_id')

            if not ticket.can_split():
                return jsonify({'success': False, 'message': 'Ticket cannot be split'}), 400

            if num_tickets < 2 or num_tickets > 10:
                return jsonify({'success': False, 'message': 'Number of tickets must be between 2 and 10'}), 400

            # Perform split
            child_tickets = ticket.split_into(
                num_tickets=num_tickets,
                agent_id=agent_id,
                assignees=assignees,
                split_criteria=split_criteria
            )

            return jsonify({
                'success': True,
                'message': f'Ticket {ticket.ticket_number} split into {num_tickets} tickets',
                'parent_ticket_id': ticket.id,
                'parent_ticket_number': ticket.ticket_number,
                'child_tickets': [{
                    'id': child.id,
                    'ticket_number': child.ticket_number,
                    'subject': child.subject
                } for child in child_tickets]
            })

        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error splitting ticket: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error splitting ticket: {str(e)}'}), 500

    @app.route('/api/ticket/<int:ticket_id>/link', methods=['POST'])
    def link_ticket(ticket_id):
        """Link ticket to another ticket"""
        try:
            source_ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()

            data = request.get_json()
            target_ticket_id = data.get('target_ticket_id')
            relationship_type = data.get('relationship_type', 'linked_to')
            metadata = data.get('metadata')
            agent_id = data.get('agent_id')

            if not target_ticket_id:
                return jsonify({'success': False, 'message': 'Target ticket ID required'}), 400

            target_ticket = Ticket.query.filter(Ticket.id == target_ticket_id, Ticket.is_deleted == False).first()
            if not target_ticket:
                return jsonify({'success': False, 'message': 'Target ticket not found'}), 404

            # Validate relationship type
            valid_types = ['linked_to', 'related_to', 'duplicate_of']
            if relationship_type not in valid_types:
                return jsonify({'success': False, 'message': f'Invalid relationship type. Must be one of: {", ".join(valid_types)}'}), 400

            # Create link
            relationship = source_ticket.link_to(
                target_ticket,
                relationship_type=relationship_type,
                agent_id=agent_id,
                metadata=metadata
            )

            return jsonify({
                'success': True,
                'message': f'Ticket {source_ticket.ticket_number} linked to {target_ticket.ticket_number}',
                'source_ticket_id': source_ticket.id,
                'target_ticket_id': target_ticket.id,
                'relationship_type': relationship_type,
                'relationship_id': relationship.id
            })

        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error linking ticket: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error linking ticket: {str(e)}'}), 500

    @app.route('/api/ticket/<int:ticket_id>/unlink/<int:relationship_id>', methods=['DELETE'])
    def unlink_ticket(ticket_id, relationship_id):
        """Remove link between tickets"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            relationship = TicketRelationship.query.get_or_404(relationship_id)

            # Verify relationship belongs to this ticket
            if relationship.source_ticket_id != ticket.id and relationship.target_ticket_id != ticket.id:
                return jsonify({'success': False, 'message': 'Relationship does not belong to this ticket'}), 403

            # Get the other ticket ID for response
            other_ticket_id = relationship.target_ticket_id if relationship.source_ticket_id == ticket.id else relationship.source_ticket_id

            # Delete the relationship
            db.session.delete(relationship)

            # Also delete reverse relationship if it exists
            reverse_rel = TicketRelationship.query.filter_by(
                source_ticket_id=other_ticket_id,
                target_ticket_id=ticket.id,
                relationship_type=relationship.relationship_type
            ).first()
            if reverse_rel:
                db.session.delete(reverse_rel)

            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Tickets unlinked successfully'
            })

        except Exception as e:
            logger.error(f"Error unlinking ticket: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error unlinking ticket: {str(e)}'}), 500

    @app.route('/api/ticket/<int:ticket_id>/relationships', methods=['GET'])
    def get_ticket_relationships(ticket_id):
        """Get all relationships for a ticket"""
        try:
            ticket = Ticket.query.filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first_or_404()
            relationships = ticket.get_related_tickets()

            # Format relationships for display
            formatted_relationships = []
            seen_pairs = set()  # Track seen ticket pairs to avoid duplicates

            for rel in relationships:
                # Determine which ticket is "other"
                is_source = rel.source_ticket_id == ticket.id
                other_ticket = rel.target_ticket if is_source else rel.source_ticket

                # Create a unique pair identifier
                pair_id = tuple(sorted([ticket.id, other_ticket.id]))
                relationship_key = (pair_id, rel.relationship_type)

                # Skip if we've already seen this relationship
                if relationship_key in seen_pairs:
                    continue
                seen_pairs.add(relationship_key)

                formatted_relationships.append({
                    'id': rel.id,
                    'type': rel.relationship_type,
                    'direction': 'outgoing' if is_source else 'incoming',
                    'ticket': {
                        'id': other_ticket.id,
                        'number': other_ticket.ticket_number,
                        'subject': other_ticket.subject,
                        'status': other_ticket.status,
                        'priority': other_ticket.priority
                    }
                })

            # Also include merged_into and parent relationships
            if ticket.merged_into:
                formatted_relationships.append({
                    'type': 'merged_into',
                    'direction': 'outgoing',
                    'ticket': {
                        'id': ticket.merged_into.id,
                        'number': ticket.merged_into.ticket_number,
                        'subject': ticket.merged_into.subject,
                        'status': ticket.merged_into.status
                    }
                })

            if ticket.parent_ticket:
                formatted_relationships.append({
                    'type': 'split_from',
                    'direction': 'outgoing',
                    'ticket': {
                        'id': ticket.parent_ticket.id,
                        'number': ticket.parent_ticket.ticket_number,
                        'subject': ticket.parent_ticket.subject,
                        'status': ticket.parent_ticket.status
                    }
                })

            # Check for children (split tickets)
            child_tickets = Ticket.query.filter_by(parent_ticket_id=ticket.id, is_deleted=False).all()
            for child in child_tickets:
                formatted_relationships.append({
                    'type': 'split_into',
                    'direction': 'outgoing',
                    'ticket': {
                        'id': child.id,
                        'number': child.ticket_number,
                        'subject': child.subject,
                        'status': child.status
                    }
                })

            # Return HTML for HTMX
            if len(formatted_relationships) == 0:
                return '<div class="text-sm text-gray-500 italic">No related tickets</div>'

            return render_template('components/ticket_relationships.html', relationships=formatted_relationships, current_ticket_id=ticket.id)

        except Exception as e:
            logger.error(f"Error getting ticket relationships: {str(e)}")
            return '<div class="text-sm text-red-500">Error loading relationships</div>'

    # Route aliases for template compatibility
    @app.route('/api/ticket/<int:ticket_id>/follower/<int:agent_id>', methods=['DELETE'])
    def remove_follower(ticket_id, agent_id):
        """Alias for remove_ticket_follower to match template expectations"""
        return remove_ticket_follower(ticket_id, agent_id)

    @app.route('/api/ticket/<int:ticket_id>/tag/<int:tag_id>', methods=['DELETE'])
    def remove_tag_from_ticket(ticket_id, tag_id):
        """Alias for remove_ticket_tag to match template expectations"""
        return remove_ticket_tag(ticket_id, tag_id)


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

        # Enable WAL mode for SQLite to prevent locking issues
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            from sqlalchemy import event, text

            @event.listens_for(db.engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=15000")
                cursor.close()

            # Apply pragmas to current connection
            with db.engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA busy_timeout=15000"))
                conn.commit()

            logger.info("SQLite WAL mode enabled for better concurrency")

        # Initialize default settings
        Settings.initialize_defaults()

        # Migrate settings from .env if they exist and database settings are empty
        migrate_env_to_settings()
        logger.info("Settings initialized")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5001)