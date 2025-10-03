from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Association tables for many-to-many relationships
ticket_tags = db.Table('ticket_tags',
    db.Column('ticket_id', db.Integer, db.ForeignKey('tickets.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

class TicketRelationship(db.Model):
    """Ticket relationship model for merge, split, and link operations"""

    __tablename__ = 'ticket_relationships'

    id = db.Column(db.Integer, primary_key=True)
    source_ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True)
    target_ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True)
    relationship_type = db.Column(db.String(20), nullable=False, index=True)  # merged_into, split_from, linked_to, duplicate_of, related_to
    relation_metadata = db.Column(db.Text)  # JSON field for additional context
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('agents.id'), index=True)

    # Relationships
    source_ticket = db.relationship('Ticket', foreign_keys=[source_ticket_id], backref='outgoing_relationships')
    target_ticket = db.relationship('Ticket', foreign_keys=[target_ticket_id], backref='incoming_relationships')
    creator = db.relationship('Agent', backref='created_relationships')

    # Unique constraint to prevent duplicate relationships
    __table_args__ = (
        db.UniqueConstraint('source_ticket_id', 'target_ticket_id', 'relationship_type', name='uq_ticket_relationship'),
    )

    def __repr__(self):
        return f'<TicketRelationship {self.source_ticket_id} {self.relationship_type} {self.target_ticket_id}>'

    def get_metadata(self):
        """Parse metadata from JSON"""
        if self.relation_metadata:
            try:
                return json.loads(self.relation_metadata)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, data):
        """Set metadata as JSON"""
        if data:
            self.relation_metadata = json.dumps(data)
        else:
            self.relation_metadata = None

    def to_dict(self):
        """Convert relationship to dictionary"""
        return {
            'id': self.id,
            'source_ticket_id': self.source_ticket_id,
            'target_ticket_id': self.target_ticket_id,
            'relationship_type': self.relationship_type,
            'metadata': self.get_metadata(),
            'created_at': self.created_at.isoformat(),
            'created_by': {
                'id': self.creator.id,
                'full_name': self.creator.full_name
            } if self.creator else None
        }

class Agent(db.Model):
    """Agent/User model for ticket management system"""

    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='agent', nullable=False)  # admin, manager, agent
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    avatar_url = db.Column(db.String(500))
    timezone = db.Column(db.String(50), default='UTC')
    language = db.Column(db.String(10), default='en')
    signature = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    assigned_tickets = db.relationship('Ticket', foreign_keys='Ticket.assignee_id', backref='assignee', lazy='dynamic')
    followed_tickets = db.relationship('TicketFollower', back_populates='agent', lazy='dynamic')
    replies = db.relationship('TicketReply', backref='agent', lazy='dynamic')

    def __repr__(self):
        return f'<Agent {self.username}: {self.first_name} {self.last_name}>'

    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password"""
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        """Get full name"""
        return f"{self.first_name} {self.last_name}"

    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin'

    def is_manager(self):
        """Check if user is manager or above"""
        return self.role in ['admin', 'manager']

class Organization(db.Model):
    """Organization model for customer companies"""

    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    domain = db.Column(db.String(255), unique=True, index=True)  # email domain for auto-assignment
    description = db.Column(db.Text)
    website = db.Column(db.String(500))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    industry = db.Column(db.String(100))
    size = db.Column(db.String(20))  # small, medium, large, enterprise
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tickets = db.relationship('Ticket', backref='organization', lazy='dynamic')

    def __repr__(self):
        return f'<Organization {self.name}>'

class TicketType(db.Model):
    """Ticket type model for categorization"""

    __tablename__ = 'ticket_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6B7280')  # hex color code
    icon = db.Column(db.String(50))  # icon name/class
    default_priority = db.Column(db.Integer, default=3)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tickets = db.relationship('Ticket', backref='ticket_type', lazy='dynamic')

    def __repr__(self):
        return f'<TicketType {self.name}>'

class Tag(db.Model):
    """Tag model for ticket labeling"""

    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#3B82F6')  # hex color code
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Tag {self.name}>'

class Status(db.Model):
    """Status model for ticket status management"""

    __tablename__ = 'statuses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6B7280')  # hex color code
    is_closed_status = db.Column(db.Boolean, default=False, nullable=False)  # True for solved/closed statuses
    display_order = db.Column(db.Integer, default=0)  # Order in which statuses appear
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Status {self.name}>'

class TicketReply(db.Model):
    """Reply/Comment model for ticket responses"""

    __tablename__ = 'ticket_replies'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=True, nullable=False)  # True for public, False for internal notes
    is_system = db.Column(db.Boolean, default=False)  # True for system-generated messages
    reply_type = db.Column(db.String(20), default='reply')  # reply, note, status_change
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    attachments = db.relationship('ReplyAttachment', backref='reply', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<TicketReply {self.id} for Ticket {self.ticket_id}>'

    def get_relative_time(self):
        """Get human-readable relative time"""
        if not self.created_at:
            return "Unknown"

        now = datetime.utcnow()
        diff = now - self.created_at

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

class TicketFollower(db.Model):
    """Follower model for agent subscriptions to tickets"""

    __tablename__ = 'ticket_followers'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    ticket = db.relationship('Ticket', backref='followers')
    agent = db.relationship('Agent', back_populates='followed_tickets')

    # Unique constraint
    __table_args__ = (db.UniqueConstraint('ticket_id', 'agent_id'),)

    def __repr__(self):
        return f'<TicketFollower: Agent {self.agent_id} follows Ticket {self.ticket_id}>'

class ReplyAttachment(db.Model):
    """Attachment model for reply attachments"""

    __tablename__ = 'reply_attachments'

    id = db.Column(db.Integer, primary_key=True)
    reply_id = db.Column(db.Integer, db.ForeignKey('ticket_replies.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100))
    size = db.Column(db.Integer)  # File size in bytes
    storage_path = db.Column(db.String(500), nullable=False)  # Path where file is stored locally
    checksum = db.Column(db.String(64))  # MD5/SHA hash for integrity
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<ReplyAttachment {self.filename} for Reply {self.reply_id}>'

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

class Ticket(db.Model):
    """Ticket model for storing email-derived tickets and future ticket sources"""

    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    source = db.Column(db.String(20), nullable=False, default='email')  # email, chat, form, api, etc.
    source_id = db.Column(db.String(255), nullable=False, index=True)  # email Message-ID, etc.
    channel = db.Column(db.String(20), default='email')  # email, web, phone, chat, api

    # Content fields
    subject = db.Column(db.Text, nullable=False)
    content_text = db.Column(db.Text)
    content_html = db.Column(db.Text)
    topic = db.Column(db.String(255))  # Main topic/category

    # Contact information
    sender_email = db.Column(db.String(255), nullable=False, index=True)  # requester_email
    sender_name = db.Column(db.String(255))
    recipient_email = db.Column(db.String(255))
    cc_emails = db.Column(db.Text)  # JSON field for CC recipients
    language = db.Column(db.String(10), default='en')  # ISO language code
    country = db.Column(db.String(3))  # ISO country code

    # Assignment and organization
    assignee_id = db.Column(db.Integer, db.ForeignKey('agents.id'), index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), index=True)
    type_id = db.Column(db.Integer, db.ForeignKey('ticket_types.id'), index=True)

    # Priority and urgency
    priority = db.Column(db.Integer, default=3)  # 1-5, default 3
    urgency = db.Column(db.Integer, default=3)  # 1-5, separate from priority

    # Status and workflow
    status = db.Column(db.String(20), default='new', index=True)  # new, open, pending, on-hold, solved, closed
    resolution = db.Column(db.Text)  # Resolution notes
    due_date = db.Column(db.DateTime, index=True)
    resolution_time = db.Column(db.Interval)  # Time taken to resolve

    # Satisfaction and feedback
    satisfaction_rating = db.Column(db.Integer)  # 1-5 rating
    satisfaction_comment = db.Column(db.Text)

    # SLA and escalation
    sla_policy_id = db.Column(db.Integer)  # Reference to SLA policy (future)
    escalation_level = db.Column(db.Integer, default=0)  # 0 = no escalation

    # Metadata
    raw_headers = db.Column(db.Text)  # JSON field storing email headers
    extra_data = db.Column(db.Text)  # JSON field for extensible source-specific data
    notes = db.Column(db.Text)  # Internal notes
    is_read = db.Column(db.Boolean, default=False, nullable=False)  # Read/unread status
    first_read_at = db.Column(db.DateTime, index=True)  # When ticket was first read
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)  # Soft delete flag
    deleted_at = db.Column(db.DateTime, index=True)  # When ticket was deleted
    deleted_by = db.Column(db.Integer, db.ForeignKey('agents.id'))  # Who deleted the ticket

    # Merge/Split tracking
    is_merged = db.Column(db.Boolean, default=False, nullable=False, index=True)  # True if ticket was merged into another
    merged_into_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), index=True)  # Target ticket if merged
    parent_ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), index=True)  # Original ticket if this is a split

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    received_at = db.Column(db.DateTime, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    first_reply_at = db.Column(db.DateTime, index=True)  # Time of first agent response
    solved_at = db.Column(db.DateTime, index=True)  # When ticket was marked solved
    closed_at = db.Column(db.DateTime, index=True)  # When ticket was closed

    # Relationships
    attachments = db.relationship('Attachment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    replies = db.relationship('TicketReply', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    tags = db.relationship('Tag', secondary=ticket_tags, lazy='subquery', backref=db.backref('tickets', lazy=True))
    deleter = db.relationship('Agent', foreign_keys=[deleted_by], backref='deleted_tickets')
    merged_into = db.relationship('Ticket', foreign_keys=[merged_into_id], remote_side='Ticket.id', backref='merged_tickets')
    parent_ticket = db.relationship('Ticket', foreign_keys=[parent_ticket_id], remote_side='Ticket.id', backref='split_tickets')

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

    def mark_as_read(self, agent_id=None):
        """Mark ticket as read"""
        if not self.is_read:
            self.is_read = True
            self.first_read_at = datetime.utcnow()
            db.session.commit()

            # Log activity
            TicketActivity.log_activity(
                ticket_id=self.id,
                activity_type='read_status_change',
                description='Ticket marked as read',
                agent_id=agent_id,
                old_value='unread',
                new_value='read',
                is_public=False  # Internal activity, not shown to customers
            )

    def mark_as_unread(self, agent_id=None):
        """Mark ticket as unread"""
        if self.is_read:  # Only log if actually changing from read to unread
            self.is_read = False
            # Don't change first_read_at as it tracks when it was first read
            db.session.commit()

            # Log activity
            TicketActivity.log_activity(
                ticket_id=self.id,
                activity_type='read_status_change',
                description='Ticket marked as unread',
                agent_id=agent_id,
                old_value='read',
                new_value='unread',
                is_public=False  # Internal activity, not shown to customers
            )
        else:
            # Still commit any other potential changes
            db.session.commit()

    def soft_delete(self, agent_id=None):
        """Soft delete the ticket"""
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = datetime.utcnow()
            self.deleted_by = agent_id
            db.session.commit()

            # Log activity
            TicketActivity.log_activity(
                ticket_id=self.id,
                activity_type='ticket_deleted',
                description='Ticket deleted',
                agent_id=agent_id,
                old_value='active',
                new_value='deleted',
                is_public=False  # Internal activity, not shown to customers
            )

    def restore(self, agent_id=None):
        """Restore a soft-deleted ticket"""
        if self.is_deleted:
            self.is_deleted = False
            self.deleted_at = None
            self.deleted_by = None
            db.session.commit()

            # Log activity
            TicketActivity.log_activity(
                ticket_id=self.id,
                activity_type='ticket_restored',
                description='Ticket restored from deletion',
                agent_id=agent_id,
                old_value='deleted',
                new_value='active',
                is_public=False  # Internal activity, not shown to customers
            )

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

    def is_open(self):
        """Check if ticket is open (active)"""
        return self.status in ['new', 'open', 'pending']

    def is_resolved(self):
        """Check if ticket is resolved"""
        return self.status in ['solved', 'closed']

    def is_assigned(self):
        """Check if ticket is assigned to an agent"""
        return self.assignee_id is not None

    def has_due_date(self):
        """Check if ticket has a due date"""
        return self.due_date is not None

    def is_overdue(self):
        """Check if ticket is overdue"""
        if not self.due_date:
            return False
        return datetime.utcnow() > self.due_date and not self.is_resolved()

    def get_priority_label(self):
        """Get priority label"""
        priority_labels = {1: 'Urgent', 2: 'High', 3: 'Normal', 4: 'Low', 5: 'Lowest'}
        return priority_labels.get(self.priority, 'Normal')

    def get_urgency_label(self):
        """Get urgency label"""
        urgency_labels = {1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low', 5: 'Lowest'}
        return urgency_labels.get(self.urgency, 'Medium')

    def get_status_label(self):
        """Get formatted status label"""
        status_labels = {
            'new': 'New',
            'open': 'Open',
            'pending': 'Pending',
            'on-hold': 'On Hold',
            'solved': 'Solved',
            'closed': 'Closed'
        }
        return status_labels.get(self.status, 'Unknown')

    def get_assignee_name(self):
        """Get assignee full name or None"""
        return self.assignee.full_name if self.assignee else None

    def get_organization_name(self):
        """Get organization name or None"""
        return self.organization.name if self.organization else None

    def get_type_name(self):
        """Get ticket type name or None"""
        return self.ticket_type.name if self.ticket_type else None

    def get_tag_names(self):
        """Get list of tag names"""
        return [tag.name for tag in self.tags]

    def add_tag(self, tag):
        """Add a tag to this ticket"""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag):
        """Remove a tag from this ticket"""
        if tag in self.tags:
            self.tags.remove(tag)

    def get_public_replies(self):
        """Get public replies only"""
        return self.replies.filter_by(is_public=True).order_by(TicketReply.created_at.desc())

    def get_internal_notes(self):
        """Get internal notes only"""
        return self.replies.filter_by(is_public=False).order_by(TicketReply.created_at.desc())

    def get_reply_count(self):
        """Get total reply count"""
        return self.replies.count()

    def get_public_reply_count(self):
        """Get public reply count"""
        return self.replies.filter_by(is_public=True).count()

    def assign_to(self, agent):
        """Assign ticket to an agent"""
        self.assignee_id = agent.id if agent else None
        self.updated_at = datetime.utcnow()

    def set_status(self, status):
        """Set ticket status with timestamp tracking"""
        old_status = self.status
        self.status = status
        self.updated_at = datetime.utcnow()

        # Set timestamps based on status
        if status == 'solved' and old_status != 'solved':
            self.solved_at = datetime.utcnow()
        elif status == 'closed' and old_status != 'closed':
            self.closed_at = datetime.utcnow()
            # Calculate resolution time if not already calculated
            if not self.resolution_time and self.created_at:
                self.resolution_time = datetime.utcnow() - self.created_at

    def calculate_age_hours(self):
        """Calculate ticket age in hours"""
        if not self.created_at:
            return 0
        return (datetime.utcnow() - self.created_at).total_seconds() / 3600

    def calculate_resolution_hours(self):
        """Calculate resolution time in hours"""
        if self.resolution_time:
            return self.resolution_time.total_seconds() / 3600
        return None

    def get_followers_list(self):
        """Get list of agents following this ticket"""
        return [follower.agent for follower in self.followers]

    def add_follower(self, agent):
        """Add an agent as follower"""
        from database.models import TicketFollower  # Import here to avoid circular import
        existing = TicketFollower.query.filter_by(ticket_id=self.id, agent_id=agent.id).first()
        if not existing:
            follower = TicketFollower(ticket_id=self.id, agent_id=agent.id)
            db.session.add(follower)

    def remove_follower(self, agent):
        """Remove an agent as follower"""
        from database.models import TicketFollower  # Import here to avoid circular import
        follower = TicketFollower.query.filter_by(ticket_id=self.id, agent_id=agent.id).first()
        if follower:
            db.session.delete(follower)

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

    # Relationship methods
    def get_related_tickets(self, relationship_type=None):
        """Get all related tickets, optionally filtered by relationship type"""
        relationships = []

        # Get outgoing relationships
        query = TicketRelationship.query.filter_by(source_ticket_id=self.id)
        if relationship_type:
            query = query.filter_by(relationship_type=relationship_type)
        relationships.extend(query.all())

        # Get incoming relationships (for bidirectional queries)
        query = TicketRelationship.query.filter_by(target_ticket_id=self.id)
        if relationship_type:
            query = query.filter_by(relationship_type=relationship_type)
        relationships.extend(query.all())

        return relationships

    def link_to(self, target_ticket, relationship_type='linked_to', agent_id=None, metadata=None):
        """Create a link to another ticket"""
        if self.id == target_ticket.id:
            raise ValueError("Cannot link ticket to itself")

        # Check for existing relationship
        existing = TicketRelationship.query.filter_by(
            source_ticket_id=self.id,
            target_ticket_id=target_ticket.id,
            relationship_type=relationship_type
        ).first()

        if existing:
            return existing

        # Create bidirectional relationships
        forward_rel = TicketRelationship(
            source_ticket_id=self.id,
            target_ticket_id=target_ticket.id,
            relationship_type=relationship_type,
            created_by=agent_id
        )
        if metadata:
            forward_rel.set_metadata(metadata)

        db.session.add(forward_rel)

        # Create reverse relationship for linked_to and related_to types
        if relationship_type in ['linked_to', 'related_to']:
            reverse_rel = TicketRelationship(
                source_ticket_id=target_ticket.id,
                target_ticket_id=self.id,
                relationship_type=relationship_type,
                created_by=agent_id
            )
            if metadata:
                reverse_rel.set_metadata(metadata)
            db.session.add(reverse_rel)

        db.session.commit()

        # Log activity
        TicketActivity.log_activity(
            ticket_id=self.id,
            activity_type='ticket_linked',
            description=f'Linked to ticket {target_ticket.ticket_number}',
            agent_id=agent_id,
            new_value=str(target_ticket.id),
            is_public=False
        )

        TicketActivity.log_activity(
            ticket_id=target_ticket.id,
            activity_type='ticket_linked',
            description=f'Linked from ticket {self.ticket_number}',
            agent_id=agent_id,
            new_value=str(self.id),
            is_public=False
        )

        return forward_rel

    def merge_into(self, target_ticket, agent_id=None, merge_replies=True, merge_tags=True, close_source=True):
        """Merge this ticket into another ticket"""
        if self.id == target_ticket.id:
            raise ValueError("Cannot merge ticket into itself")

        if self.is_merged:
            raise ValueError("This ticket has already been merged")

        # Transfer replies if requested
        if merge_replies:
            for reply in self.replies.all():
                reply.ticket_id = target_ticket.id
                # Add note indicating origin
                if not reply.content.startswith('[Merged from'):
                    reply.content = f"[Merged from {self.ticket_number}]\n\n{reply.content}"

        # Merge tags if requested
        if merge_tags:
            for tag in self.tags:
                if tag not in target_ticket.tags:
                    target_ticket.tags.append(tag)

        # Transfer followers
        for follower in self.followers:
            if follower.agent not in target_ticket.get_followers_list():
                target_ticket.add_follower(follower.agent)

        # Create relationship
        relationship = TicketRelationship(
            source_ticket_id=self.id,
            target_ticket_id=target_ticket.id,
            relationship_type='merged_into',
            created_by=agent_id
        )
        relationship.set_metadata({
            'merge_replies': merge_replies,
            'merge_tags': merge_tags,
            'original_status': self.status
        })
        db.session.add(relationship)

        # Update this ticket's status
        self.is_merged = True
        self.merged_into_id = target_ticket.id
        if close_source:
            self.status = 'closed'
            self.closed_at = datetime.utcnow()

        db.session.commit()

        # Log activities
        TicketActivity.log_activity(
            ticket_id=self.id,
            activity_type='ticket_merged',
            description=f'Merged into ticket {target_ticket.ticket_number}',
            agent_id=agent_id,
            old_value=self.status,
            new_value='merged',
            is_public=False
        )

        TicketActivity.log_activity(
            ticket_id=target_ticket.id,
            activity_type='ticket_merge_received',
            description=f'Ticket {self.ticket_number} merged into this ticket',
            agent_id=agent_id,
            new_value=str(self.id),
            is_public=False
        )

        return relationship

    def split_into(self, num_tickets, agent_id=None, assignees=None, split_criteria=None):
        """Split this ticket into multiple child tickets"""
        if num_tickets < 2:
            raise ValueError("Must split into at least 2 tickets")

        child_tickets = []

        for i in range(num_tickets):
            # Create child ticket
            child = Ticket(
                ticket_number=Ticket.create_unique_ticket_number(),
                source=self.source,
                source_id=f"{self.source_id}_split_{i+1}",
                channel=self.channel,
                subject=f"{self.subject} [Split {i+1}/{num_tickets}]",
                content_text=self.content_text,
                content_html=self.content_html,
                sender_email=self.sender_email,
                sender_name=self.sender_name,
                recipient_email=self.recipient_email,
                organization_id=self.organization_id,
                type_id=self.type_id,
                priority=self.priority,
                urgency=self.urgency,
                status='new',
                received_at=datetime.utcnow(),
                parent_ticket_id=self.id
            )

            # Assign if specified
            if assignees and i < len(assignees):
                child.assignee_id = assignees[i]

            # Copy tags
            for tag in self.tags:
                child.tags.append(tag)

            db.session.add(child)
            child_tickets.append(child)

        # Flush to get IDs for child tickets before creating relationships
        db.session.flush()

        # Create relationships after flush
        for i, child in enumerate(child_tickets):
            relationship = TicketRelationship(
                source_ticket_id=child.id,
                target_ticket_id=self.id,
                relationship_type='split_from',
                created_by=agent_id
            )
            if split_criteria:
                relationship.set_metadata({'criteria': split_criteria, 'split_index': i+1, 'total_splits': num_tickets})
            db.session.add(relationship)

        db.session.commit()

        # Log activity on parent
        TicketActivity.log_activity(
            ticket_id=self.id,
            activity_type='ticket_split',
            description=f'Split into {num_tickets} tickets: {", ".join([t.ticket_number for t in child_tickets])}',
            agent_id=agent_id,
            new_value=str(num_tickets),
            is_public=False
        )

        # Log activity on each child
        for child in child_tickets:
            TicketActivity.log_activity(
                ticket_id=child.id,
                activity_type='ticket_split_created',
                description=f'Created from split of ticket {self.ticket_number}',
                agent_id=agent_id,
                new_value=str(self.id),
                is_public=False
            )

        return child_tickets

    def unlink_from(self, target_ticket_id, relationship_type=None):
        """Remove link to another ticket"""
        query = TicketRelationship.query.filter_by(
            source_ticket_id=self.id,
            target_ticket_id=target_ticket_id
        )
        if relationship_type:
            query = query.filter_by(relationship_type=relationship_type)

        relationships = query.all()
        for rel in relationships:
            db.session.delete(rel)

        # Also remove reverse relationships
        query = TicketRelationship.query.filter_by(
            source_ticket_id=target_ticket_id,
            target_ticket_id=self.id
        )
        if relationship_type:
            query = query.filter_by(relationship_type=relationship_type)

        reverse_rels = query.all()
        for rel in reverse_rels:
            db.session.delete(rel)

        db.session.commit()

    def can_merge(self):
        """Check if ticket can be merged"""
        return not self.is_merged and not self.is_deleted and self.status not in ['closed', 'archived']

    def can_split(self):
        """Check if ticket can be split"""
        return not self.is_merged and not self.is_deleted and len(self.split_tickets) == 0

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


class TicketActivity(db.Model):
    """Track all activities/changes on tickets for timeline display"""
    __tablename__ = 'ticket_activities'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)  # Nullable for system activities
    activity_type = db.Column(db.String(50), nullable=False)  # status_change, assignment, reply, priority_change, etc.
    description = db.Column(db.Text, nullable=False)  # Human-readable activity description
    old_value = db.Column(db.Text, nullable=True)  # Previous value (for changes)
    new_value = db.Column(db.Text, nullable=True)  # New value (for changes)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_public = db.Column(db.Boolean, default=True, nullable=False)  # Whether visible to customers

    # Relationships
    ticket = db.relationship('Ticket', backref=db.backref('activities', lazy='dynamic', order_by='TicketActivity.created_at.desc()'))
    agent = db.relationship('Agent', backref='activities')

    def __repr__(self):
        return f'<TicketActivity {self.activity_type} on Ticket {self.ticket_id} at {self.created_at}>'

    @classmethod
    def log_activity(cls, ticket_id, activity_type, description, agent_id=None, old_value=None, new_value=None, is_public=True):
        """Log a new activity for a ticket"""
        activity = cls(
            ticket_id=ticket_id,
            agent_id=agent_id,
            activity_type=activity_type,
            description=description,
            old_value=old_value,
            new_value=new_value,
            is_public=is_public
        )
        db.session.add(activity)
        db.session.commit()
        return activity

    def to_dict(self):
        """Convert activity to dictionary for API responses"""
        return {
            'id': self.id,
            'activity_type': self.activity_type,
            'description': self.description,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'created_at': self.created_at.isoformat(),
            'is_public': self.is_public,
            'agent': {
                'id': self.agent.id,
                'full_name': self.agent.full_name
            } if self.agent else None
        }

class SavedFilter(db.Model):
    """Saved filter model for storing user-defined ticket filters"""

    __tablename__ = 'saved_filters'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Filter metadata
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    # Ownership
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False, index=True)

    # Filter criteria (stored as JSON)
    filter_criteria = db.Column(db.Text, nullable=False)

    # Filter preferences
    is_default = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_favorite = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_shared = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent = db.relationship('Agent', backref='saved_filters')

    # Indexes
    __table_args__ = (
        db.Index('idx_agent_default', 'agent_id', 'is_default'),
        db.Index('idx_agent_favorite', 'agent_id', 'is_favorite'),
    )

    def __repr__(self):
        return f'<SavedFilter {self.name} by Agent {self.agent_id}>'

    def get_criteria(self):
        """Parse filter criteria from JSON"""
        if self.filter_criteria:
            try:
                return json.loads(self.filter_criteria)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_criteria(self, data):
        """Set filter criteria as JSON"""
        if data:
            self.filter_criteria = json.dumps(data)
        else:
            self.filter_criteria = '{}'

    def to_dict(self):
        """Convert saved filter to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'criteria': self.get_criteria(),
            'is_default': self.is_default,
            'is_favorite': self.is_favorite,
            'is_shared': self.is_shared,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'agent': {
                'id': self.agent.id,
                'full_name': self.agent.full_name
            } if self.agent else None
        }