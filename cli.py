#!/usr/bin/env python3
"""
Respondr CLI - Command Line Interface

Provides convenient commands for managing the Respondr application.
"""

import os
import sys
import click
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@click.group()
def cli():
    """Respondr Command Line Interface"""
    pass


@cli.command()
@click.option('--interval', default=300, type=int, help='Sync interval in seconds (default: 300)')
@click.option('--once', is_flag=True, help='Run sync once and exit')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def sync(interval, once, debug):
    """
    Run email synchronization scheduler

    Examples:
        respondr sync                       # Run with default 5-minute interval
        respondr sync --interval 60         # Run with 1-minute interval
        respondr sync --once                # Run once and exit
        respondr sync --debug               # Run with debug logging
    """
    from scheduler import main as scheduler_main

    # Construct args
    args = ['scheduler.py']
    if once:
        args.append('--once')
    if debug:
        args.append('--debug')
    if not once:
        args.extend(['--interval', str(interval)])

    # Set sys.argv for argparse in scheduler
    sys.argv = args

    click.echo(f"Starting email sync scheduler...")
    if once:
        click.echo("Mode: One-time sync")
    else:
        click.echo(f"Mode: Continuous (interval: {interval} seconds)")

    scheduler_main()


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
@click.option('--port', default=5000, type=int, help='Port to bind to (default: 5000)')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.option('--no-scheduler', is_flag=True, help='Disable email sync scheduler')
def run(host, port, debug, no_scheduler):
    """
    Run the Respondr web application

    Examples:
        respondr run                        # Run with default settings
        respondr run --port 8080            # Run on custom port
        respondr run --debug                # Run in debug mode
        respondr run --no-scheduler         # Run without email scheduler
    """
    from app import create_app

    click.echo(f"Starting Respondr web application...")
    click.echo(f"Server: http://{host}:{port}")
    click.echo(f"Debug mode: {'enabled' if debug else 'disabled'}")
    click.echo(f"Email scheduler: {'disabled' if no_scheduler else 'enabled'}")

    # Create app
    app = create_app()

    # Override scheduler setting
    if no_scheduler:
        app.config['SCHEDULER_ENABLED'] = False

    # Run app
    app.run(host=host, port=port, debug=debug)


@cli.command()
def migrate():
    """Run database migrations"""
    from app import create_app
    from database.migrations import (
        migrate_add_ticket_relationships,
        migrate_add_soft_delete,
        migrate_add_saved_filters
    )

    click.echo("Running database migrations...")
    app = create_app()

    migrations = [
        ('Ticket Relationships', migrate_add_ticket_relationships),
        ('Soft Delete', migrate_add_soft_delete),
        ('Saved Filters', migrate_add_saved_filters),
    ]

    for name, migration_func in migrations:
        try:
            click.echo(f"Running migration: {name}...", nl=False)
            migration_func(app)
            click.echo(" ✓", fg='green')
        except Exception as e:
            click.echo(f" ✗ Error: {str(e)}", fg='red')

    click.echo("Migrations completed!")


@cli.command()
@click.option('--tables', is_flag=True, help='Show database tables')
@click.option('--settings', is_flag=True, help='Show application settings')
@click.option('--stats', is_flag=True, help='Show statistics')
def info(tables, settings, stats):
    """Display application information"""
    from app import create_app
    from database.models import db, Ticket, Agent, Organization, TicketType, Tag, Settings

    app = create_app()

    with app.app_context():
        if tables:
            click.echo("\n=== Database Tables ===")
            inspector = db.inspect(db.engine)
            for table_name in inspector.get_table_names():
                click.echo(f"  • {table_name}")

        if settings:
            click.echo("\n=== Application Settings ===")
            all_settings = Settings.query.all()
            if all_settings:
                for setting in all_settings:
                    click.echo(f"  {setting.key}: {setting.value}")
            else:
                click.echo("  No settings found")

        if stats:
            click.echo("\n=== Statistics ===")
            click.echo(f"  Tickets: {Ticket.query.filter_by(is_deleted=False).count()}")
            click.echo(f"  Agents: {Agent.query.filter_by(is_active=True).count()}")
            click.echo(f"  Organizations: {Organization.query.count()}")
            click.echo(f"  Ticket Types: {TicketType.query.filter_by(is_active=True).count()}")
            click.echo(f"  Tags: {Tag.query.filter_by(is_active=True).count()}")

        if not (tables or settings or stats):
            click.echo("\n=== Respondr Application Info ===")
            click.echo(f"  Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
            click.echo(f"  Debug: {app.config['DEBUG']}")
            click.echo(f"  Scheduler: {'enabled' if app.config.get('SCHEDULER_ENABLED', True) else 'disabled'}")
            click.echo("\nUse --tables, --settings, or --stats for detailed information")


@cli.command()
@click.confirmation_option(prompt='This will DELETE all existing tickets. Continue?')
def demo():
    """
    Create demo/sample tickets for testing and demonstration

    WARNING: This will delete all existing tickets and create 15 realistic sample tickets.

    Examples:
        respondr demo   # Create demo data (with confirmation prompt)
    """
    import subprocess
    import sys

    click.echo("Creating demo data...")

    result = subprocess.run(
        [sys.executable, 'create_demo_data.py'],
        input=b'yes\n',
        capture_output=True
    )

    # Print output
    if result.stdout:
        click.echo(result.stdout.decode())
    if result.stderr:
        click.echo(result.stderr.decode(), err=True)

    if result.returncode == 0:
        click.echo("✅ Demo data created successfully!")
    else:
        click.echo("❌ Failed to create demo data")
        sys.exit(1)


if __name__ == '__main__':
    cli()
