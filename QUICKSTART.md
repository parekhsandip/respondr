# Respondr Quick Start Guide

Get Respondr up and running in minutes!

## Prerequisites

- Python 3.8+
- Virtual environment activated
- Gmail account with App Password (for email sync)

## Installation

1. **Clone and setup virtual environment:**
   ```bash
   cd /path/to/respondr
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install click  # For CLI tools
   ```

3. **Configure email settings:**

   Create a `.env` file in the project root:
   ```bash
   # Email Configuration
   IMAP_SERVER=imap.gmail.com
   IMAP_PORT=993
   IMAP_USERNAME=your-email@gmail.com
   IMAP_PASSWORD=your-app-password
   IMAP_FOLDER=INBOX

   # Optional: Disable in-app scheduler (recommended)
   SCHEDULER_ENABLED=False
   ```

   **Gmail App Password Setup:**
   1. Go to https://myaccount.google.com/security
   2. Enable 2-Step Verification
   3. Generate App Password: https://myaccount.google.com/apppasswords
   4. Use this password in IMAP_PASSWORD

4. **Initialize database:**
   ```bash
   python cli.py migrate
   ```

## Running the Application

### Option 1: All-in-One (Development)

Run both web app and email sync together:

```bash
# Terminal 1: Web Application
python cli.py run --debug

# Terminal 2: Email Sync Scheduler
python cli.py sync --interval 60
```

### Option 2: Web Only

Run just the web application (manual email sync):

```bash
python cli.py run
```

Visit: http://127.0.0.1:5000

### Option 3: Production Setup

```bash
# Terminal 1: Web App with Gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 4 "app:create_app()"

# Terminal 2: Email Sync Scheduler
python scheduler.py --interval 300  # 5 minutes
```

## Common Commands

### Web Application

```bash
# Start on custom port
python cli.py run --port 8080

# Start without scheduler
python cli.py run --no-scheduler

# Debug mode
python cli.py run --debug
```

### Email Sync

```bash
# Run scheduler (default 5-min interval)
python cli.py sync

# Custom interval (1 minute)
python cli.py sync --interval 60

# One-time sync (testing)
python cli.py sync --once

# Debug mode
python cli.py sync --debug
```

### Database

```bash
# Run migrations
python cli.py migrate

# View statistics
python cli.py info --stats

# View settings
python cli.py info --settings
```

## Background/Daemon Mode

### Using nohup (Linux/macOS)

```bash
# Start scheduler in background
nohup python scheduler.py --interval 300 > logs/scheduler.log 2>&1 &

# Check if running
ps aux | grep scheduler.py

# Stop
pkill -f scheduler.py
```

### Using systemd (Linux)

1. Create service file: `/etc/systemd/system/respondr-scheduler.service`
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

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable respondr-scheduler
   sudo systemctl start respondr-scheduler
   sudo systemctl status respondr-scheduler
   ```

## First Time Setup

1. **Access the application:**
   - Open: http://127.0.0.1:5000
   - Default page shows inbox

2. **Configure settings:**
   - Click Settings (⚙️ icon)
   - Verify email configuration
   - Set sync intervals
   - Create ticket types and tags

3. **Manual sync (first time):**
   ```bash
   python cli.py sync --once
   ```

4. **Verify tickets:**
   - Refresh inbox
   - Check for imported emails
   - Assign tickets to agents
   - Apply tags and types

## Troubleshooting

### No emails syncing

```bash
# Test email connection
python cli.py sync --once --debug

# Check logs
tail -f logs/scheduler.log

# Verify credentials
python cli.py info --settings
```

### Database locked errors

```bash
# Ensure only one scheduler is running
ps aux | grep scheduler
pkill -f scheduler  # Kill all

# Check scheduler is disabled in app
python cli.py run --no-scheduler
```

### Port already in use

```bash
# Find process using port 5000
lsof -i :5000

# Run on different port
python cli.py run --port 8080
```

## Next Steps

- 📚 Read [CLI_GUIDE.md](CLI_GUIDE.md) for detailed CLI usage
- 📖 See [README.md](README.md) for full documentation
- 🏗️ Check [project_structure.md](project_structure.md) for architecture

## Quick Reference

| Task | Command |
|------|---------|
| Start web app | `python cli.py run` |
| Start scheduler | `python cli.py sync` |
| One-time sync | `python cli.py sync --once` |
| Run migrations | `python cli.py migrate` |
| View stats | `python cli.py info --stats` |
| Debug mode | `python cli.py run --debug` |
| Custom port | `python cli.py run --port 8080` |

---

**Need Help?** Check the logs in `logs/` directory or run commands with `--debug` flag for verbose output.
