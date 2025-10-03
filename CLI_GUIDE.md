# Respondr CLI Guide

This guide explains how to use the Respondr command-line interface for managing the application and running the email sync scheduler independently.

## Table of Contents

- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Email Sync Scheduler](#email-sync-scheduler)
- [Database Migrations](#database-migrations)
- [Application Information](#application-information)

---

## Installation

Ensure you have activated your virtual environment:

```bash
source venv/bin/activate  # On Linux/macOS
# or
venv\Scripts\activate  # On Windows
```

Install required dependencies (if not already installed):

```bash
pip install click
```

---

## Running the Application

### Start Web Application

**Basic usage:**
```bash
python cli.py run
```

**Custom host and port:**
```bash
python cli.py run --host 0.0.0.0 --port 8080
```

**Debug mode:**
```bash
python cli.py run --debug
```

**Disable email scheduler (recommended for production):**
```bash
python cli.py run --no-scheduler
```

**Complete example:**
```bash
python cli.py run --host 0.0.0.0 --port 8080 --no-scheduler
```

### Options:
- `--host` - Host to bind to (default: 127.0.0.1)
- `--port` - Port to bind to (default: 5000)
- `--debug` - Enable debug mode
- `--no-scheduler` - Disable email sync scheduler in the app

---

## Email Sync Scheduler

The email sync scheduler has been separated from the main application for better control and scalability.

### Run Scheduler (Continuous Mode)

**Basic usage (5-minute interval):**
```bash
python cli.py sync
```

**Custom interval (1 minute):**
```bash
python cli.py sync --interval 60
```

**With debug logging:**
```bash
python cli.py sync --debug
```

### Run Once (One-time Sync)

Useful for testing or manual sync:

```bash
python cli.py sync --once
```

### Direct Scheduler Usage

You can also run the scheduler directly:

```bash
# Continuous mode
python scheduler.py --interval 300

# One-time sync
python scheduler.py --once

# Debug mode
python scheduler.py --debug
```

### Background/Daemon Mode

**Using nohup (Linux/macOS):**
```bash
nohup python scheduler.py --interval 300 > logs/scheduler.log 2>&1 &
```

**Using systemd (Linux):**

Create `/etc/systemd/system/respondr-scheduler.service`:

```ini
[Unit]
Description=Respondr Email Sync Scheduler
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/respondr
ExecStart=/path/to/respondr/venv/bin/python scheduler.py --interval 300
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable respondr-scheduler
sudo systemctl start respondr-scheduler
sudo systemctl status respondr-scheduler
```

**Using supervisor (Linux/macOS):**

Create `/etc/supervisor/conf.d/respondr-scheduler.conf`:

```ini
[program:respondr-scheduler]
command=/path/to/respondr/venv/bin/python /path/to/respondr/scheduler.py --interval 300
directory=/path/to/respondr
user=your-username
autostart=true
autorestart=true
stderr_logfile=/var/log/respondr-scheduler.err.log
stdout_logfile=/var/log/respondr-scheduler.out.log
```

Then:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start respondr-scheduler
```

---

## Database Migrations

Run all pending database migrations:

```bash
python cli.py migrate
```

This will execute:
- Ticket Relationships migration
- Soft Delete migration
- Saved Filters migration

---

## Application Information

### View All Settings

```bash
python cli.py info
```

### View Database Tables

```bash
python cli.py info --tables
```

### View Application Settings

```bash
python cli.py info --settings
```

### View Statistics

```bash
python cli.py info --stats
```

Example output:
```
=== Statistics ===
  Tickets: 150
  Agents: 5
  Organizations: 12
  Ticket Types: 8
  Tags: 25
```

---

## Production Deployment Recommendations

### Recommended Setup

1. **Run Web App without scheduler:**
   ```bash
   gunicorn --bind 0.0.0.0:8000 --workers 4 "app:create_app()"
   ```

2. **Run Scheduler as separate service:**
   ```bash
   python scheduler.py --interval 300
   ```

3. **Use process manager** (systemd, supervisor, or PM2) to manage both processes

### Why Separate Scheduler?

- **Better resource management**: Email sync doesn't block web requests
- **Independent scaling**: Can run scheduler on different server
- **Easier debugging**: Separate logs for sync and web traffic
- **Graceful restarts**: Restart web app without affecting email sync
- **Flexibility**: Different sync intervals without restarting web app

---

## Environment Variables

Set these in your `.env` file or environment:

```bash
# Scheduler Control
SCHEDULER_ENABLED=False  # Disable in-app scheduler (use standalone)

# Email Sync Settings
FETCH_INTERVAL=300  # Sync interval in seconds (default: 5 minutes)
MAX_EMAILS_PER_SYNC=50  # Maximum emails to fetch per sync

# Email Configuration
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=your-email@gmail.com
IMAP_PASSWORD=your-app-password
IMAP_FOLDER=INBOX
```

---

## Troubleshooting

### Scheduler not syncing

1. Check logs: `tail -f logs/scheduler.log`
2. Verify email credentials in settings
3. Test one-time sync: `python cli.py sync --once --debug`

### Both app and scheduler running

If both are syncing, you may see duplicate emails. To fix:
- Set `SCHEDULER_ENABLED=False` in config
- Or run app with `--no-scheduler` flag

### Permission errors

Make scripts executable:
```bash
chmod +x scheduler.py cli.py
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `python cli.py run` | Start web application |
| `python cli.py run --no-scheduler` | Start web app without scheduler |
| `python cli.py sync` | Run email scheduler (5-min interval) |
| `python cli.py sync --interval 60` | Run scheduler (1-min interval) |
| `python cli.py sync --once` | Run one-time email sync |
| `python cli.py migrate` | Run database migrations |
| `python cli.py info` | Show application info |
| `python cli.py info --stats` | Show statistics |
| `python scheduler.py` | Direct scheduler (no CLI wrapper) |

---

## Support

For issues or questions:
- Check logs in `logs/` directory
- Run with `--debug` flag for verbose output
- Review email settings in database
