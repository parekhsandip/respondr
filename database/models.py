from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Ticket(db.Model):
    """Ticket model for storing email-derived tickets and future ticket sources"""

    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    source = db.Column(db.String(20), nullable=False, default='email')  # email, chat, form, api, etc.
    source_id = db.Column(db.String(255), nullable=False, index=True)  # email Message-ID, etc.
    subject = db.Column(db.Text, nullable=False)
    content_text = db.Column(db.Text)
    content_html = db.Column(db.Text)
    sender_email = db.Column(db.String(255), nullable=False, index=True)
    sender_name = db.Column(db.String(255))
    recipient_email = db.Column(db.String(255))
    cc_emails = db.Column(db.Text)  # JSON field for CC recipients
    priority = db.Column(db.Integer, default=3)  # 1-5, default 3
    status = db.Column(db.String(20), default='new', index=True)  # new, read, archived
    raw_headers = db.Column(db.Text)  # JSON field storing email headers
    extra_data = db.Column(db.Text)  # JSON field for extensible source-specific data
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    received_at = db.Column(db.DateTime, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    attachments = db.relationship('Attachment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Ticket {self.ticket_number}: {self.subject[:50]}>'

    def get_cc_emails(self):
        """Parse CC emails from JSON"""
        if self.cc_emails:
            try:
                return json.loads(self.cc_emails)
            except json.JSONDecodeError:
                return []
        return []

    def set_cc_emails(self, emails):
        """Set CC emails as JSON"""
        if emails:
            self.cc_emails = json.dumps(emails)
        else:
            self.cc_emails = None

    def get_raw_headers(self):
        """Parse raw headers from JSON"""
        if self.raw_headers:
            try:
                return json.loads(self.raw_headers)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_raw_headers(self, headers):
        """Set raw headers as JSON"""
        if headers:
            self.raw_headers = json.dumps(headers)
        else:
            self.raw_headers = None

    def get_extra_data(self):
        """Parse extra data from JSON"""
        if self.extra_data:
            try:
                return json.loads(self.extra_data)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_extra_data(self, data):
        """Set extra data as JSON"""
        if data:
            self.extra_data = json.dumps(data)
        else:
            self.extra_data = None

    def is_unread(self):
        """Check if ticket is unread"""
        return self.status == 'new'

    def has_attachments(self):
        """Check if ticket has non-embedded attachments"""
        return self.attachments.filter_by(is_embedded=False).count() > 0

    def get_attachment_count(self):
        """Get count of non-embedded attachments"""
        return self.attachments.filter_by(is_embedded=False).count()

    def get_relative_time(self):
        """Get human-readable relative time"""
        if not self.received_at:
            return "Unknown"

        now = datetime.utcnow()
        diff = now - self.received_at

        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"

    def get_content_preview(self, max_length=100):
        """Get truncated content preview"""
        content = self.content_text or self.content_html or ""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."

    @staticmethod
    def generate_ticket_number():
        """Generate unique ticket number"""
        from datetime import datetime
        import random
        import string

        # Get current date
        now = datetime.utcnow()
        date_part = now.strftime("%Y%m%d")

        # Generate random suffix
        suffix = ''.join(random.choices(string.digits, k=4))

        return f"TKT-{date_part}-{suffix}"

    @classmethod
    def create_unique_ticket_number(cls):
        """Create a unique ticket number, handling collisions"""
        max_attempts = 10
        for _ in range(max_attempts):
            ticket_number = cls.generate_ticket_number()
            if not cls.query.filter_by(ticket_number=ticket_number).first():
                return ticket_number

        # Fallback with timestamp if we can't generate unique number
        import time
        timestamp = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
        return f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{timestamp}"


class Attachment(db.Model):
    """Attachment model for storing file attachments"""

    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100))
    size = db.Column(db.Integer)  # File size in bytes
    storage_path = db.Column(db.String(500), nullable=False)  # Path where file is stored locally
    checksum = db.Column(db.String(64))  # MD5/SHA hash for integrity
    content_id = db.Column(db.String(255))  # Content-ID for embedded images (CID)
    is_embedded = db.Column(db.Boolean, default=False)  # True for inline/embedded attachments
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Attachment {self.filename} for Ticket {self.ticket_id}>'

    def get_file_size_human(self):
        """Get human-readable file size"""
        if not self.size:
            return "Unknown size"

        size = self.size
        units = ['B', 'KB', 'MB', 'GB']
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.1f} {units[unit_index]}"

    def is_image(self):
        """Check if attachment is an image"""
        if not self.content_type:
            return False
        return self.content_type.startswith('image/')

    def is_document(self):
        """Check if attachment is a document"""
        if not self.content_type:
            return False
        document_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain',
            'text/csv'
        ]
        return self.content_type in document_types


class Settings(db.Model):
    """Application settings stored in database"""

    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), default='general', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Setting {self.key}: {self.value}>'

    @classmethod
    def get(cls, key, default=None):
        """Get setting value by key"""
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set(cls, key, value, description=None, category='general'):
        """Set setting value"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value) if value is not None else None
            setting.updated_at = datetime.utcnow()
            if description:
                setting.description = description
            if category:
                setting.category = category
        else:
            setting = cls(
                key=key,
                value=str(value) if value is not None else None,
                description=description,
                category=category
            )
            db.session.add(setting)
        db.session.commit()
        return setting

    @classmethod
    def get_by_category(cls, category):
        """Get all settings in a category"""
        return cls.query.filter_by(category=category).all()

    @classmethod
    def get_email_config(cls):
        """Get email configuration as dictionary"""
        email_settings = cls.query.filter_by(category='email').all()
        config = {}
        for setting in email_settings:
            # Convert string values to appropriate types
            if setting.key in ['IMAP_PORT', 'SMTP_PORT', 'FETCH_INTERVAL', 'MAX_EMAILS_PER_SYNC', 'ATTACHMENT_MAX_SIZE']:
                config[setting.key] = int(setting.value) if setting.value else 0
            elif setting.key in ['IMAP_USE_SSL', 'SCHEDULER_ENABLED']:
                config[setting.key] = setting.value.lower() == 'true' if setting.value else False
            else:
                config[setting.key] = setting.value
        return config

    @classmethod
    def initialize_defaults(cls):
        """Initialize default settings"""
        defaults = [
            # Email settings
            ('IMAP_SERVER', 'imap.gmail.com', 'IMAP server hostname', 'email'),
            ('IMAP_PORT', '993', 'IMAP server port', 'email'),
            ('IMAP_USERNAME', '', 'Email username', 'email'),
            ('IMAP_PASSWORD', '', 'Email password', 'email'),
            ('IMAP_USE_SSL', 'true', 'Use SSL for IMAP connection', 'email'),
            ('IMAP_FOLDER', 'INBOX', 'Email folder to monitor', 'email'),
            ('SMTP_SERVER', 'smtp.gmail.com', 'SMTP server hostname', 'email'),
            ('SMTP_PORT', '587', 'SMTP server port', 'email'),

            # Sync settings
            ('FETCH_INTERVAL', '300', 'Email fetch interval in seconds', 'sync'),
            ('MAX_EMAILS_PER_SYNC', '10', 'Maximum emails to fetch per sync', 'sync'),
            ('SCHEDULER_ENABLED', 'true', 'Enable automatic email syncing', 'sync'),

            # File settings
            ('ATTACHMENT_MAX_SIZE', '10485760', 'Maximum attachment size in bytes', 'files'),
            ('ATTACHMENT_STORAGE_PATH', 'storage/attachments', 'Directory for attachment storage', 'files'),

            # App settings
            ('TICKETS_PER_PAGE', '20', 'Number of tickets per page', 'app'),
        ]

        for key, value, description, category in defaults:
            if not cls.query.filter_by(key=key).first():
                cls.set(key, value, description, category)


class EmailSyncLog(db.Model):
    """Log table for tracking email synchronization operations"""

    __tablename__ = 'email_sync_logs'

    id = db.Column(db.Integer, primary_key=True)
    sync_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    emails_fetched = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), nullable=False)  # success, failure, partial
    error_message = db.Column(db.Text)
    last_uid = db.Column(db.String(50))  # Last processed email UID for IMAP
    duration_seconds = db.Column(db.Float)  # Sync duration

    def __repr__(self):
        return f'<EmailSyncLog {self.sync_time}: {self.status}>'

    @classmethod
    def log_sync(cls, emails_fetched=0, status='success', error_message=None, last_uid=None, duration=None):
        """Log a sync operation"""
        log_entry = cls(
            emails_fetched=emails_fetched,
            status=status,
            error_message=error_message,
            last_uid=last_uid,
            duration_seconds=duration
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry

    @classmethod
    def get_last_successful_sync(cls):
        """Get the last successful sync log entry"""
        return cls.query.filter_by(status='success').order_by(cls.sync_time.desc()).first()

    @classmethod
    def get_last_uid(cls):
        """Get the last processed UID from successful syncs"""
        last_sync = cls.get_last_successful_sync()
        return last_sync.last_uid if last_sync else None