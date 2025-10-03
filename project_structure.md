# Respondr Project Structure

A comprehensive Zendesk-like ticket management system built with Flask, SQLAlchemy, and SQLite.

## Project Overview
Enterprise-grade ticketing system with agent management, organization tracking, ticket types, tags, public/private replies, follower notifications, and enhanced status workflows.

## Directory Structure

```
respondr/
├── .env                           # Environment variables (email config, secrets)
├── .gitignore                     # Git ignore patterns
├── CLAUDE.md                      # Claude development instructions and context
├── CLI_GUIDE.md                   # CLI usage guide and deployment instructions
├── LICENSE                        # MIT License
├── README.md                      # Project documentation
├── app.py                         # Main Flask application with routes and API endpoints
├── app_context.md                 # Application context and configuration details
├── cli.py                         # Command-line interface for app and scheduler management
├── config.py                      # Flask configuration settings
├── migrate_database.py            # Database migration script for schema updates
├── project_req.md                 # Project requirements and specifications
├── requirements.txt               # Python dependencies
├── scheduler.py                   # Standalone email sync scheduler (independent process)
├── setup.py                       # Package setup and installation script
│
├── database/                      # Database layer
│   ├── __init__.py
│   ├── models.py                  # SQLAlchemy models (Ticket, Agent, Organization, etc.)
│   └── migrations.py              # Database migration utilities and default data
│
├── services/                      # Business logic layer
│   ├── __init__.py
│   ├── email_fetcher.py           # IMAP email synchronization service
│   └── ticket_service.py          # Ticket processing and management logic
│
├── templates/                     # Jinja2 HTML templates
│   ├── base.html                  # Base template with navigation and layout (uses external CSS/JS)
│   ├── inbox.html                 # Ticket list/inbox view with modal functionality
│   ├── settings.html              # Application settings page with AJAX forms
│   ├── ticket_view.html           # Detailed ticket view with replies and metadata
│   ├── ticket_view_new.html       # Enhanced ticket view with improved UI
│   └── components/
│       ├── ticket_list.html       # Reusable ticket list component
│       └── ticket_table.html      # Table component with sorting and bulk actions
│
├── static/                        # Static assets with versioning for cache busting
│   ├── css/
│   │   ├── base.css               # Common styles (HTMX, scrollbars, transitions, sidebar)
│   │   ├── components/            # Component-specific styles (reserved for future use)
│   │   └── pages/                 # Page-specific styles (reserved for future use)
│   └── js/
│       ├── base.js                # Global utilities (toast notifications, HTMX handlers)
│       ├── components/            # Component-specific JavaScript (reserved for future use)
│       ├── pages/
│       │   ├── inbox.js           # Inbox functionality (modals, ticket operations)
│       │   └── settings.js        # Settings page functionality (forms, API calls)
│       └── utils/                 # Utility functions (reserved for future use)
│
├── storage/                       # File storage directory
│   └── attachments/               # Email attachment storage
│
├── instance/                      # Flask instance folder
│   ├── tickets.db                 # Main SQLite database (active)
│   └── tickets.db.backup.*        # Database backups from migrations
│
└── venv/                          # Python virtual environment
    └── (standard virtual env structure)
```

## Key Components

### Core Application Files

#### `app.py` (Main Application)
- Flask app factory and configuration
- **Asset versioning system** for cache busting (based on file modification time)
- API endpoints for all features:
  - `/api/agents` - Agent management
  - `/api/ticket/<id>/assign` - Ticket assignment (handles both JSON and form data)
  - `/api/tickets/<id>/replies` - Reply system
  - `/api/ticket-types`, `/api/tags` - Metadata management
  - `/api/settings` - Settings management with database storage
  - `/api/saved-filters` - Saved filter management (list, create, update, delete)
  - `/api/filter-options` - Available filter options
  - `/api/tickets/search` - Advanced search with multi-select filtering
- Web routes for UI pages
- **Optional** in-app scheduler (disabled by default, use standalone scheduler.py)

#### `scheduler.py` (Standalone Email Sync)
- **Independent email synchronization process** (separate from web app)
- APScheduler with background threading
- Configurable sync interval via CLI arguments
- Graceful shutdown handling (SIGINT, SIGTERM)
- Comprehensive logging to `logs/scheduler.log`
- One-time sync mode for testing
- **Recommended for production** - runs as separate service

#### `cli.py` (Command-Line Interface)
- **Unified CLI for application management**
- Commands:
  - `python cli.py run` - Start web application
  - `python cli.py sync` - Run email sync scheduler
  - `python cli.py migrate` - Run database migrations
  - `python cli.py info` - Display app info and statistics
- Built with Click framework
- See [CLI_GUIDE.md](CLI_GUIDE.md) for detailed usage

#### `config.py` (Configuration)
- Database URI: `sqlite:///instance/tickets.db` (resolves to `instance/tickets.db`)
- Email settings (IMAP/SMTP)
- Security and pagination settings
- **SCHEDULER_ENABLED**: Default `False` (use standalone scheduler)
- Environment variable integration


### Services Layer

#### `services/email_fetcher.py`
- IMAP email synchronization
- Email parsing and ticket creation
- Attachment handling and storage
- Duplicate detection and threading

#### `services/ticket_service.py`
- Business logic for ticket operations
- Status workflow management
- Assignment and notification logic
- Search and filtering capabilities

### Templates (UI Layer)

#### Enhanced UI Features:
- **Responsive design** with Tailwind CSS
- **Interactive elements** with HTMX
- **Modular architecture** with external CSS/JS files
- **Cache busting** with versioned static assets (`?v=timestamp`)
- **Separation of concerns**:
  - Common styles in `static/css/base.css`
  - Page-specific JavaScript in `static/js/pages/`
  - Global utilities in `static/js/base.js`

#### Asset Organization:
- **CSS**: Extracted from inline `<style>` tags to external files
- **JavaScript**: Separated global functions from page-specific code
- **Versioning**: All static files include modification time for cache invalidation

## Database Schema

### Current Database: `instance/tickets.db`
- **14 tables** with proper relationships and foreign keys
- **Performance indexes** on frequently queried columns
- **Migration support** for schema updates

### Key Relationships:
- Tickets → Agents (assignee)
- Tickets → Organizations (customer)
- Tickets → TicketTypes (categorization)
- Tickets ↔ Tags (many-to-many)
- Tickets → Statuses (workflow state)
- Tickets → TicketReplies (one-to-many)
- Tickets ↔ TicketFollowers (many-to-many)
- SavedFilters → Agents (owner)


### Environment Requirements:
- Python 3.13+ with virtual environment at `venv/`
- SQLite database (no external DB required)
- Email credentials for IMAP sync (optional)

### Key Dependencies:
- Flask 3.1+ (web framework)
- SQLAlchemy 2.0+ (ORM)
- Flask-APScheduler (job scheduling)
- Tailwind CSS (styling)
- HTMX (dynamic interactions)
