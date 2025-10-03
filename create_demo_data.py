#!/usr/bin/env python3
"""
Create Demo Data for Respondr

This script cleans the database and creates realistic sample tickets for demonstration.
"""

import os
import sys
from datetime import datetime, timedelta
import random

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from database.models import (
    db, Ticket, Agent, Organization, TicketType, Tag, Status,
    TicketReply, TicketActivity, Attachment
)

# Sample data
SAMPLE_TICKETS = [
    {
        'subject': 'Unable to login to customer portal',
        'sender_name': 'Sarah Johnson',
        'sender_email': 'sarah.johnson@techcorp.com',
        'organization': 'TechCorp Industries',
        'content': '''Hi Support Team,

I've been trying to access the customer portal for the past hour, but I keep getting an "Invalid credentials" error. I'm certain my password is correct as I have it saved in my password manager.

I've tried:
- Clearing my browser cache
- Using a different browser (Chrome and Firefox)
- Resetting my password

The issue persists. This is urgent as I need to access our invoices for the quarterly review today.

Can you please help?

Best regards,
Sarah Johnson
IT Manager, TechCorp Industries''',
        'priority': 2,
        'urgency': 1,
        'status': 'open',
        'type': 'Bug',
        'tags': ['urgent', 'login-issue'],
        'days_ago': 0,
        'replies': [
            {
                'content': 'Hi Sarah,\n\nThank you for reaching out. I see you\'re having login issues. Let me check your account status.\n\nI\'ve verified that your account is active. Can you confirm if you\'re receiving any specific error codes?\n\nBest regards,\nSupport Team',
                'is_public': True,
                'hours_ago': 2
            }
        ]
    },
    {
        'subject': 'Feature Request: Dark Mode for Mobile App',
        'sender_name': 'Michael Chen',
        'sender_email': 'm.chen@innovatetech.io',
        'organization': 'InnovateTech Solutions',
        'content': '''Hello,

I'd like to suggest adding a dark mode option to your mobile application. Many users, including myself, prefer dark interfaces especially when using the app in low-light environments.

This would be a great addition to enhance user experience and reduce eye strain during evening use.

Benefits:
- Reduced battery consumption on OLED screens
- Better accessibility for users with light sensitivity
- Modern UI/UX trend that users expect

Looking forward to your consideration!

Thanks,
Michael Chen
Product Manager''',
        'priority': 4,
        'urgency': 4,
        'status': 'pending',
        'type': 'Feature Request',
        'tags': ['enhancement', 'mobile'],
        'days_ago': 1
    },
    {
        'subject': 'Billing discrepancy on Invoice #INV-2024-1234',
        'sender_name': 'Emily Rodriguez',
        'sender_email': 'emily.rodriguez@globalent.com',
        'organization': 'Global Enterprises LLC',
        'content': '''Dear Billing Department,

I noticed a discrepancy on our latest invoice (INV-2024-1234). We were charged for 50 user licenses, but we only have 35 active users in our account.

Could you please review this and issue a corrected invoice?

Invoice Details:
- Invoice Number: INV-2024-1234
- Amount Charged: $2,500
- Expected Amount: $1,750
- Difference: $750

I've attached our current user list for your reference.

Please let me know how we can resolve this.

Best regards,
Emily Rodriguez
Finance Director''',
        'priority': 2,
        'urgency': 2,
        'status': 'solved',
        'type': 'Billing',
        'tags': ['billing', 'invoice'],
        'days_ago': 3,
        'replies': [
            {
                'content': 'Dear Emily,\n\nThank you for bringing this to our attention. I\'ve reviewed your account and confirmed the discrepancy.\n\nWe\'ll issue a credit note for $750 and send you a corrected invoice within 24 hours.\n\nApologies for the inconvenience.\n\nBest regards,\nBilling Team',
                'is_public': True,
                'hours_ago': 48
            }
        ]
    },
    {
        'subject': 'API Integration Documentation Missing',
        'sender_name': 'David Kumar',
        'sender_email': 'david.k@devstudio.dev',
        'organization': 'DevStudio',
        'content': '''Hi Team,

I'm trying to integrate your API into our application, but I can't find the documentation for the webhook endpoints. The main API docs are great, but the webhook section returns a 404.

Specifically, I need information on:
1. Webhook payload structure
2. Authentication methods for webhooks
3. Retry logic for failed webhooks
4. List of available webhook events

Could you point me to the right documentation or provide this information?

This is blocking our integration timeline.

Thanks,
David Kumar
Lead Developer''',
        'priority': 2,
        'urgency': 2,
        'status': 'open',
        'type': 'Question',
        'tags': ['api', 'documentation'],
        'days_ago': 0,
        'replies': [
            {
                'content': 'Hi David,\n\nYou\'re right - we need to update our webhook documentation. I\'ve escalated this to our technical writing team.\n\nIn the meantime, I can provide you with the payload structure directly. Let me compile that information for you.\n\nBest regards,\nAPI Support',
                'is_public': True,
                'hours_ago': 1
            }
        ]
    },
    {
        'subject': 'Account Migration from Basic to Premium Plan',
        'sender_name': 'Jennifer Martinez',
        'sender_email': 'jennifer@startupxyz.com',
        'organization': 'StartupXYZ',
        'content': '''Hello,

Our team has grown and we'd like to upgrade from the Basic plan to the Premium plan. I have a few questions:

1. Will our existing data be preserved during the migration?
2. Is there any downtime during the upgrade?
3. Can we schedule the migration for a specific time?
4. Will our users need to re-authenticate after the upgrade?

Our current plan expires in 15 days. We'd like to upgrade before then.

Please let me know the next steps.

Thanks,
Jennifer Martinez
Operations Manager''',
        'priority': 3,
        'urgency': 3,
        'status': 'new',
        'type': 'Account',
        'tags': ['upgrade', 'migration'],
        'days_ago': 0
    },
    {
        'subject': 'Password Reset Email Not Received',
        'sender_name': 'Robert Wilson',
        'sender_email': 'r.wilson@techsolutions.net',
        'organization': 'Tech Solutions Inc',
        'content': '''Support Team,

I requested a password reset 30 minutes ago but haven't received the email yet. I've checked my spam folder and it's not there either.

My email is: r.wilson@techsolutions.net

Can you manually reset my password or resend the email?

I need to access the system urgently for a client meeting in 2 hours.

Thanks,
Robert Wilson''',
        'priority': 1,
        'urgency': 1,
        'status': 'open',
        'type': 'Bug',
        'tags': ['urgent', 'password-reset'],
        'days_ago': 0,
        'replies': []
    },
    {
        'subject': 'Request for Training Materials',
        'sender_name': 'Lisa Thompson',
        'sender_email': 'lisa.t@educorp.edu',
        'organization': 'EduCorp Training',
        'content': '''Dear Customer Success Team,

We've recently onboarded 20 new team members and would like to request training materials for your platform.

Do you offer:
- Video tutorials?
- PDF guides?
- Interactive training sessions?
- Certification programs?

We're planning to conduct training next week, so any materials you can provide by this Friday would be greatly appreciated.

Best regards,
Lisa Thompson
Training Coordinator''',
        'priority': 3,
        'urgency': 3,
        'status': 'pending',
        'type': 'Question',
        'tags': ['training', 'onboarding'],
        'days_ago': 2
    },
    {
        'subject': 'Data Export Failing for Large Datasets',
        'sender_name': 'Alex Patel',
        'sender_email': 'alex@dataanalytics.com',
        'organization': 'Data Analytics Pro',
        'content': '''Hi Support,

I'm experiencing issues when trying to export large datasets (>10,000 records) from the platform. The export starts but fails after about 5 minutes with a timeout error.

Steps to reproduce:
1. Navigate to Reports > Data Export
2. Select "All Records" for the past 6 months
3. Choose CSV format
4. Click Export
5. Wait 5 minutes
6. Receive timeout error

Is there a file size limit? Can you suggest an alternative approach for exporting large datasets?

This is critical for our monthly reporting.

Thanks,
Alex Patel
Data Analyst''',
        'priority': 2,
        'urgency': 2,
        'status': 'on-hold',
        'type': 'Bug',
        'tags': ['bug', 'export'],
        'days_ago': 1,
        'replies': [
            {
                'content': 'Hi Alex,\n\nThanks for the detailed report. We\'ve identified the issue - exports over 10k records require a different process.\n\nWe\'re working on a fix. As a workaround, you can export in smaller batches (5k records each).\n\nETA for fix: 2-3 business days.\n\nTechnical Support',
                'is_public': True,
                'hours_ago': 12
            }
        ]
    },
    {
        'subject': 'Security Concern: Suspicious Login Activity',
        'sender_name': 'James Anderson',
        'sender_email': 'j.anderson@securecorp.com',
        'organization': 'SecureCorp',
        'content': '''URGENT - Security Team,

I received notifications about login attempts from IP addresses in countries we don't operate in (Russia, China).

The attempts were made today at:
- 03:45 UTC from 123.45.67.89 (China)
- 04:12 UTC from 98.76.54.32 (Russia)

I've immediately changed my password, but I'm concerned about:
1. Was my account compromised?
2. What data might have been accessed?
3. Should we enable 2FA for all team members?

Please investigate this urgently and let me know the findings.

James Anderson
Security Officer''',
        'priority': 1,
        'urgency': 1,
        'status': 'open',
        'type': 'Security',
        'tags': ['urgent', 'security', 'investigation'],
        'days_ago': 0,
        'replies': [
            {
                'content': 'Hi James,\n\nWe take security very seriously. I\'ve escalated this to our security team for immediate investigation.\n\nInitial findings:\n- The login attempts were blocked by our system\n- No successful authentication occurred\n- No data was accessed\n\nWe\'ll provide a full security report within 4 hours.\n\nSecurity Team',
                'is_public': True,
                'hours_ago': 1
            }
        ]
    },
    {
        'subject': 'Mobile App Crashes on iOS 17',
        'sender_name': 'Maria Garcia',
        'sender_email': 'maria.garcia@mobiletech.com',
        'organization': 'MobileTech Solutions',
        'content': '''Hello Support,

Our team is experiencing consistent crashes of your mobile app on iOS 17 devices. The crash happens when:

1. Opening the app
2. Navigating to the Reports section
3. App freezes for 2-3 seconds
4. Then crashes completely

This started after the latest iOS 17.1 update. We've tried:
- Reinstalling the app
- Clearing cache
- Restarting devices

Device info:
- iPhone 14 Pro (iOS 17.1)
- iPhone 15 (iOS 17.0.3)
- iPad Pro M2 (iOS 17.1)

Is there a known issue? When can we expect a fix?

Maria Garcia
Mobile Team Lead''',
        'priority': 2,
        'urgency': 2,
        'status': 'open',
        'type': 'Bug',
        'tags': ['bug', 'mobile', 'ios'],
        'days_ago': 1
    },
    {
        'subject': 'Request for Custom Report Template',
        'sender_name': 'Thomas Lee',
        'sender_email': 'thomas@businessinsights.com',
        'organization': 'Business Insights Corp',
        'content': '''Dear Team,

We need a custom report template that includes:

1. Monthly revenue breakdown by product
2. Customer acquisition costs
3. Churn rate analysis
4. Regional performance metrics

The existing templates don't quite meet our needs. Is it possible to create a custom template? If so:
- What's the process?
- Is there an additional cost?
- How long would it take?

We'd need this for our Q4 board presentation.

Best regards,
Thomas Lee
CFO''',
        'priority': 3,
        'urgency': 3,
        'status': 'pending',
        'type': 'Feature Request',
        'tags': ['reporting', 'custom'],
        'days_ago': 2
    },
    {
        'subject': 'GDPR Data Deletion Request',
        'sender_name': 'Sophie Dubois',
        'sender_email': 'sophie.dubois@euroclient.fr',
        'organization': 'EuroClient SA',
        'content': '''Subject: GDPR Article 17 - Right to be Forgotten

Dear Data Protection Officer,

Under the EU General Data Protection Regulation (GDPR), Article 17, I request the complete deletion of all my personal data from your systems.

Account Details:
- Email: sophie.dubois@euroclient.fr
- Account ID: EUR-12345
- Registration Date: 2022-03-15

Please confirm:
1. When the deletion will be completed
2. What data will be retained (if any) for legal compliance
3. Process for confirming deletion

I expect this to be completed within 30 days as per GDPR requirements.

Thank you,
Sophie Dubois''',
        'priority': 1,
        'urgency': 2,
        'status': 'new',
        'type': 'Compliance',
        'tags': ['gdpr', 'legal', 'data-deletion'],
        'days_ago': 0
    },
    {
        'subject': 'Integration with Salesforce - Setup Help',
        'sender_name': 'Kevin Brown',
        'sender_email': 'kevin.brown@salestech.io',
        'organization': 'SalesTech Innovations',
        'content': '''Hi Integration Team,

We're trying to set up the Salesforce integration but running into authentication issues.

Current status:
✅ Connected our Salesforce account
✅ Granted necessary permissions
❌ Getting "OAuth token expired" error
❌ Data sync not working

Questions:
1. How often does the OAuth token need to be refreshed?
2. Is there a webhook we should configure?
3. Can you provide step-by-step setup instructions?

We need this working before our sales team training session on Friday.

Thanks,
Kevin Brown
Sales Operations Manager''',
        'priority': 2,
        'urgency': 2,
        'status': 'open',
        'type': 'Integration',
        'tags': ['integration', 'salesforce'],
        'days_ago': 1
    },
    {
        'subject': 'Performance Issues During Peak Hours',
        'sender_name': 'Rachel Kim',
        'sender_email': 'rachel@fastgrowth.com',
        'organization': 'FastGrowth Startup',
        'content': '''Support Team,

We're experiencing significant performance degradation during peak hours (9 AM - 12 PM EST):

Symptoms:
- Page load times: 5-10 seconds (normal: 1-2 seconds)
- API response times: 3-5 seconds (normal: 200-500ms)
- Occasional timeouts on dashboard

This is affecting our customer-facing operations and causing complaints.

Our usage stats:
- 500 active users
- 50,000 API calls/day
- Premium plan

Is this a known issue? Are we hitting any rate limits? Should we consider upgrading our plan?

Looking forward to your investigation.

Rachel Kim
CTO''',
        'priority': 1,
        'urgency': 1,
        'status': 'open',
        'type': 'Performance',
        'tags': ['urgent', 'performance'],
        'days_ago': 0,
        'replies': [
            {
                'content': 'Hi Rachel,\n\nWe\'ve identified increased load on our infrastructure during those hours. Our engineering team is investigating.\n\nImmediate actions:\n- Scaled up server capacity\n- Optimized database queries\n- Implemented caching for your account\n\nYou should see improvements within the next hour. We\'ll monitor closely.\n\nInfrastructure Team',
                'is_public': True,
                'hours_ago': 0.5
            }
        ]
    },
    {
        'subject': 'Thank you for the excellent support!',
        'sender_name': 'Amanda Foster',
        'sender_email': 'amanda@happyclient.com',
        'organization': 'Happy Client Co',
        'content': '''Dear Support Team,

I just wanted to send a quick note to thank you for the outstanding support we received last week.

Our issue was resolved quickly and professionally. The support agent (Tom) went above and beyond to ensure everything was working perfectly.

We've been customers for 2 years and the service quality has consistently exceeded our expectations. Keep up the great work!

Best regards,
Amanda Foster
CEO''',
        'priority': 5,
        'urgency': 5,
        'status': 'closed',
        'type': 'Feedback',
        'tags': ['positive', 'feedback'],
        'days_ago': 5,
        'replies': [
            {
                'content': 'Dear Amanda,\n\nThank you so much for your kind words! We\'ve shared your feedback with Tom and the entire team.\n\nCustomer satisfaction is our top priority, and it\'s wonderful to hear we\'re meeting your expectations.\n\nWe look forward to continuing to serve you!\n\nBest regards,\nCustomer Success Team',
                'is_public': True,
                'hours_ago': 120
            }
        ]
    }
]


def clean_database(app):
    """Remove all tickets and related data"""
    print("\n🗑️  Cleaning database...")

    with app.app_context():
        try:
            # Delete in correct order to respect foreign keys
            TicketActivity.query.delete()
            print("   ✓ Deleted activities")

            TicketReply.query.delete()
            print("   ✓ Deleted replies")

            Attachment.query.delete()
            print("   ✓ Deleted attachments")

            # Clear ticket-tag associations
            db.session.execute(db.text('DELETE FROM ticket_tags'))
            print("   ✓ Cleared ticket-tag associations")

            # Delete tickets
            Ticket.query.delete()
            print("   ✓ Deleted tickets")

            db.session.commit()
            print("✅ Database cleaned successfully\n")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error cleaning database: {str(e)}")
            raise


def create_sample_tickets(app):
    """Create sample tickets with realistic data"""
    print("📝 Creating sample tickets...")

    with app.app_context():
        try:
            # Get first agent (or create one if none exists)
            agent = Agent.query.first()
            if not agent:
                print("❌ No agents found. Please create an agent first.")
                return

            # Get or create organizations
            orgs = {}
            for ticket_data in SAMPLE_TICKETS:
                org_name = ticket_data.get('organization')
                if org_name and org_name not in orgs:
                    org = Organization.query.filter_by(name=org_name).first()
                    if not org:
                        org = Organization(
                            name=org_name,
                            domain=ticket_data['sender_email'].split('@')[1]
                        )
                        db.session.add(org)
                        db.session.flush()
                    orgs[org_name] = org

            # Get or create ticket types
            types = {}
            for ticket_data in SAMPLE_TICKETS:
                type_name = ticket_data.get('type')
                if type_name and type_name not in types:
                    ticket_type = TicketType.query.filter_by(name=type_name).first()
                    if not ticket_type:
                        colors = {
                            'Bug': '#EF4444',
                            'Feature Request': '#3B82F6',
                            'Question': '#8B5CF6',
                            'Billing': '#10B981',
                            'Account': '#F59E0B',
                            'Security': '#DC2626',
                            'Integration': '#06B6D4',
                            'Performance': '#F97316',
                            'Feedback': '#22C55E',
                            'Compliance': '#6366F1'
                        }
                        ticket_type = TicketType(
                            name=type_name,
                            color=colors.get(type_name, '#6B7280'),
                            is_active=True
                        )
                        db.session.add(ticket_type)
                        db.session.flush()
                    types[type_name] = ticket_type

            # Get or create tags
            all_tags = {}
            for ticket_data in SAMPLE_TICKETS:
                for tag_name in ticket_data.get('tags', []):
                    if tag_name not in all_tags:
                        tag = Tag.query.filter_by(name=tag_name).first()
                        if not tag:
                            tag_colors = {
                                'urgent': '#DC2626',
                                'bug': '#EF4444',
                                'enhancement': '#3B82F6',
                                'mobile': '#8B5CF6',
                                'api': '#06B6D4',
                                'billing': '#10B981',
                                'security': '#DC2626',
                                'documentation': '#F59E0B'
                            }
                            tag = Tag(
                                name=tag_name,
                                color=tag_colors.get(tag_name, '#6B7280'),
                                is_active=True
                            )
                            db.session.add(tag)
                            db.session.flush()
                        all_tags[tag_name] = tag

            db.session.commit()

            # Create tickets
            created_count = 0
            for i, ticket_data in enumerate(SAMPLE_TICKETS, 1):
                # Calculate dates
                days_ago = ticket_data.get('days_ago', 0)
                created_at = datetime.utcnow() - timedelta(days=days_ago)
                received_at = created_at - timedelta(minutes=random.randint(1, 10))

                # Create ticket
                ticket = Ticket(
                    ticket_number=f'TKT-{datetime.now().strftime("%Y%m%d")}-{1000+i:04d}',
                    source='email',
                    source_id=f'demo-{i}@example.com',
                    subject=ticket_data['subject'],
                    content_text=ticket_data['content'],
                    sender_name=ticket_data['sender_name'],
                    sender_email=ticket_data['sender_email'],
                    priority=ticket_data['priority'],
                    urgency=ticket_data.get('urgency', ticket_data['priority']),
                    status=ticket_data['status'],
                    created_at=created_at,
                    received_at=received_at,
                    updated_at=created_at,
                    is_read=(ticket_data['status'] != 'new')
                )

                # Assign organization
                org_name = ticket_data.get('organization')
                if org_name and org_name in orgs:
                    ticket.organization = orgs[org_name]

                # Assign type
                type_name = ticket_data.get('type')
                if type_name and type_name in types:
                    ticket.ticket_type = types[type_name]

                # Assign to agent for some tickets
                if ticket_data['status'] in ['open', 'pending', 'on-hold', 'solved', 'closed']:
                    ticket.assignee = agent

                # Add tags
                for tag_name in ticket_data.get('tags', []):
                    if tag_name in all_tags:
                        ticket.tags.append(all_tags[tag_name])

                db.session.add(ticket)
                db.session.flush()

                # Create replies
                for reply_data in ticket_data.get('replies', []):
                    hours_ago = reply_data.get('hours_ago', 1)
                    reply_created = created_at + timedelta(hours=hours_ago)

                    reply = TicketReply(
                        ticket_id=ticket.id,
                        agent_id=agent.id,
                        content=reply_data['content'],
                        is_public=reply_data.get('is_public', True),
                        created_at=reply_created
                    )
                    db.session.add(reply)

                    # Update ticket's first_reply_at
                    if not ticket.first_reply_at or reply_created < ticket.first_reply_at:
                        ticket.first_reply_at = reply_created

                # Mark as solved/closed if applicable
                if ticket.status == 'solved':
                    ticket.solved_at = ticket.updated_at
                elif ticket.status == 'closed':
                    ticket.solved_at = ticket.updated_at - timedelta(hours=2)
                    ticket.closed_at = ticket.updated_at

                created_count += 1
                print(f"   ✓ Created ticket {i}: {ticket.subject[:50]}...")

            db.session.commit()
            print(f"\n✅ Successfully created {created_count} sample tickets!\n")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating sample tickets: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


def main():
    """Main execution"""
    print("\n" + "="*60)
    print("  Respondr Demo Data Creator")
    print("="*60)

    # Create app
    app = create_app()

    # Confirm action
    print("\n⚠️  WARNING: This will DELETE all existing tickets!")
    response = input("Are you sure you want to continue? (yes/no): ")

    if response.lower() != 'yes':
        print("\n❌ Operation cancelled.")
        return

    # Clean and create
    clean_database(app)
    create_sample_tickets(app)

    print("="*60)
    print("  ✨ Demo data created successfully!")
    print("  🌐 Access the application to view the sample tickets")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
