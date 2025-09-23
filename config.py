import os
from datetime import timedelta

class Config:
    """Application configuration"""

    # Flask settings
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///tickets.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email settings
    IMAP_SERVER = os.environ.get('IMAP_SERVER', 'imap.gmail.com')
    IMAP_PORT = int(os.environ.get('IMAP_PORT', 993))
    IMAP_USERNAME = os.environ.get('IMAP_USERNAME', '')
    IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD', '')
    IMAP_USE_SSL = os.environ.get('IMAP_USE_SSL', 'True').lower() == 'true'
    IMAP_FOLDER = os.environ.get('IMAP_FOLDER', 'INBOX')

    # SMTP settings (for future use)
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))

    # Sync settings
    FETCH_INTERVAL = int(os.environ.get('FETCH_INTERVAL', 300))  # 5 minutes
    MAX_EMAILS_PER_SYNC = int(os.environ.get('MAX_EMAILS_PER_SYNC', 50))

    # File upload settings
    ATTACHMENT_MAX_SIZE = int(os.environ.get('ATTACHMENT_MAX_SIZE', 10485760))  # 10MB
    ATTACHMENT_STORAGE_PATH = os.environ.get('ATTACHMENT_STORAGE_PATH', 'storage/attachments')

    # Scheduler settings
    SCHEDULER_ENABLED = os.environ.get('SCHEDULER_ENABLED', 'True').lower() == 'true'
    SCHEDULER_API_ENABLED = True

    # Pagination
    TICKETS_PER_PAGE = int(os.environ.get('TICKETS_PER_PAGE', 20))

    # Security settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    @staticmethod
    def validate_email_config():
        """Validate email configuration"""
        required_settings = ['IMAP_USERNAME', 'IMAP_PASSWORD']
        missing = []

        for setting in required_settings:
            if not os.environ.get(setting):
                missing.append(setting)

        if missing:
            raise ValueError(f"Missing required email configuration: {', '.join(missing)}")

        return True