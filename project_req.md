# Detailed Prompt: Build Email-to-Ticket Monitoring Application

## Project Overview
Create a Python Flask web application that monitors an email inbox via IMAP, automatically fetches new emails, stores them as tickets in a SQLite database, and provides a modern web interface to browse and view these tickets. This app will serve as the foundation for a future customer support system. The project name is "Respondr".

## Core Requirements

### 1. Database Schema (SQLite)
Design a ticket-centric database structure that can accommodate multiple ticket sources in the future. Create the following tables:

**Tickets Table:**
- `id` (primary key, auto-increment)
- `ticket_number` (unique identifier, e.g., "TKT-20240001")
- `source` (varchar: 'email', future: 'chat', 'form', 'api', etc.)
- `source_id` (unique identifier from source, e.g., email Message-ID)
- `subject` (ticket title/subject line)
- `content_text` (plain text version of content)
- `content_html` (HTML version if available)
- `sender_email` (email address of sender)
- `sender_name` (display name of sender)
- `recipient_email` (to address)
- `cc_emails` (JSON field for CC recipients)
- `priority` (integer: 1-5, default 3)
- `status` (varchar: 'new', 'read', 'archived' for now)
- `raw_headers` (JSON field storing email headers)
- `metadata` (JSON field for extensible source-specific data)
- `created_at` (timestamp when ticket was created in system)
- `received_at` (timestamp when email was actually sent)
- `updated_at` (timestamp for last update)

**Attachments Table:**
- `id` (primary key)
- `ticket_id` (foreign key to tickets)
- `filename` (original filename)
- `content_type` (MIME type)
- `size` (file size in bytes)
- `storage_path` (path where file is stored locally)
- `checksum` (MD5/SHA hash for integrity)
- `created_at` (timestamp)

**Email_Sync_Log Table:**
- `id` (primary key)
- `sync_time` (timestamp)
- `emails_fetched` (integer)
- `status` (success/failure)
- `error_message` (if any)
- `last_uid` (last processed email UID for IMAP)

### 2. Backend Implementation (Python/Flask)

**Project Structure:**
```
respondr/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── database/
│   ├── __init__.py
│   ├── models.py         # SQLAlchemy models
│   └── migrations.py     # Database initialization
├── services/
│   ├── __init__.py
│   ├── email_fetcher.py  # IMAP email fetching logic
│   └── ticket_service.py # Ticket creation/management
├── templates/             # HTML templates
│   ├── base.html
│   ├── inbox.html
│   ├── ticket_view.html
│   └── components/       # HTMX partial templates
├── static/
│   ├── css/
│   └── js/
└── storage/
    └── attachments/       # File storage directory
```

**Key Components to Implement:**

1. **Email Configuration Module:**
   - Store IMAP/SMTP settings (host, port, username, password, SSL/TLS)
   - Support for major providers (Gmail, Outlook, Yahoo, custom)
   - Configuration via environment variables or config file

2. **Email Fetcher Service:**
   - Connect to IMAP server
   - Fetch UNSEEN emails or emails since last sync
   - Parse email content (handle multipart messages)
   - Extract and save attachments
   - Convert emails to ticket format
   - Handle email threading (store References/In-Reply-To)
   - Implement error handling and retry logic

3. **Background Task Scheduler:**
   - Use Flask-APScheduler or similar
   - Poll email every X minutes (configurable)
   - Log sync operations
   - Handle connection failures gracefully

4. **Flask Routes:**
   - `/` - Dashboard/inbox view
   - `/tickets` - List all tickets (with pagination)
   - `/ticket/<id>` - View single ticket
   - `/attachment/<id>` - Download attachment
   - `/api/sync` - Manual sync trigger
   - `/api/tickets` - JSON endpoint for HTMX
   - `/api/ticket/<id>/mark-read` - Update ticket status
   - `/settings` - Email configuration page

### 3. Frontend Implementation (HTMX + Tailwind CSS)

**Design Requirements:**
- Clean, minimalist interface with a modern feel
- Responsive design that works on desktop and mobile
- Use Tailwind CSS utility classes (no custom CSS unless necessary)
- Implement HTMX for dynamic updates without page refreshes

**UI Components:**

1. **Inbox/Ticket List Page:**
   - Left sidebar with folder/status filters (New, Read, All)
   - Main content area with ticket list
   - Each ticket row shows:
     - Status indicator (blue dot for unread)
     - Sender name and email
     - Subject line (truncated)
     - Preview of content (first 100 chars)
     - Timestamp (relative: "2 hours ago")
     - Attachment indicator icon if has attachments
   - Search bar at top
   - Pagination or infinite scroll with HTMX
   - Click to view ticket (HTMX partial load)

2. **Ticket View Page:**
   - Header with sender info and subject
   - Full email content (with HTML rendering)
   - Attachment section with download buttons
   - Metadata section (collapsible): headers, source info
   - Action buttons: Mark as Read/Unread, Archive
   - Back to inbox button

3. **Visual Design:**
   - Color scheme: Clean whites/grays with blue accents
   - Typography: System fonts, clear hierarchy
   - Icons: Use Heroicons or Tabler Icons
   - Loading states: Skeleton loaders for HTMX requests
   - Empty states: Friendly messages when no tickets

### 4. Features to Implement

**Essential Features:**
1. Automatic email fetching every 5 minutes (configurable)
2. Manual sync button with loading indicator
3. Mark tickets as read/unread
4. Search tickets by subject, sender, content
5. Filter by status (new/read)
6. Sort by date (newest/oldest)
7. Attachment preview (for images) and download
8. Responsive mobile view
9. Real-time updates using HTMX polling
10. Basic error handling and user feedback

**Technical Requirements:**
1. Use SQLAlchemy ORM for database operations
2. Implement proper logging (use Python logging module)
3. Handle large emails efficiently (streaming for attachments)
4. Sanitize HTML content before displaying
5. CSRF protection for forms
6. Basic authentication for the web interface
7. Environment-based configuration
8. Graceful handling of email connection failures

### 5. Configuration & Setup

**Environment Variables:**
```
FLASK_SECRET_KEY=
DATABASE_URL=sqlite:///tickets.db
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=
IMAP_PASSWORD=
IMAP_USE_SSL=True
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
FETCH_INTERVAL=300  # seconds
MAX_EMAILS_PER_SYNC=50
ATTACHMENT_MAX_SIZE=10485760  # 10MB
```

**Initial Setup Script:**
- Create database tables
- Create storage directories
- Validate email configuration
- Perform initial sync

### 6. Code Quality Requirements

1. Follow PEP 8 Python style guidelines
2. Add docstrings to all functions and classes
3. Include inline comments for complex logic
4. Create a comprehensive README.md with:
   - Installation instructions
   - Configuration guide
   - Usage examples
   - Troubleshooting section
5. Include error messages that are user-friendly
6. Implement proper exception handling throughout

### 7. Deliverables

Create a fully functional application with:
1. All Python backend code
2. All HTML templates with HTMX integration
3. Tailwind CSS styling (use CDN for simplicity)
4. SQLite database with proper schema
5. Requirements.txt file
6. README.md with setup instructions
7. Sample .env file
8. Basic deployment instructions for local development

### 8. Testing Considerations

Include:
1. Connection test endpoint for email settings
2. Sample data seeder for development
3. Basic validation for email configuration
4. Error simulation for handling failures

## Implementation Notes

- Start with core email fetching functionality
- Ensure the ticket table structure is flexible for future sources
- Keep the UI simple but polished
- Focus on reliability over advanced features
- Make configuration easy to change without code modifications
- Design API endpoints to be RESTful for future expansion
- Use HTMX for dynamic updates to avoid complex JavaScript
- Store attachments on filesystem, not in database
- Implement pagination early to handle large email volumes

## Success Criteria

The application should:
1. Successfully connect to an email account via IMAP
2. Fetch and store emails as tickets in SQLite
3. Display tickets in a clean, modern web interface
4. Allow viewing of individual tickets and downloading attachments
5. Update in near real-time without manual page refreshes
6. Handle errors gracefully without crashing
7. Be easily configurable via environment variables
8. Run reliably as a long-running service

Build this application step by step, starting with the database schema, then the email fetching service, followed by the Flask routes, and finally the frontend interface. Make sure each component is working before moving to the next.