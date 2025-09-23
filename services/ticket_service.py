import logging
from datetime import datetime
from sqlalchemy import or_, and_
from database.models import db, Ticket, Attachment, EmailSyncLog

logger = logging.getLogger(__name__)

class TicketService:
    """Service for managing tickets and providing business logic"""

    @staticmethod
    def get_tickets(page=1, per_page=20, status_filter=None, search_query=None, sort_by='received_at', sort_order='desc'):
        """Get paginated tickets with filtering and sorting"""
        try:
            query = Ticket.query

            # Apply status filter
            if status_filter and status_filter != 'all':
                query = query.filter(Ticket.status == status_filter)

            # Apply search filter
            if search_query:
                search_terms = search_query.strip().split()
                for term in search_terms:
                    search_filter = or_(
                        Ticket.subject.contains(term),
                        Ticket.sender_name.contains(term),
                        Ticket.sender_email.contains(term),
                        Ticket.content_text.contains(term)
                    )
                    query = query.filter(search_filter)

            # Apply sorting
            if sort_by == 'received_at':
                if sort_order == 'desc':
                    query = query.order_by(Ticket.received_at.desc())
                else:
                    query = query.order_by(Ticket.received_at.asc())
            elif sort_by == 'subject':
                if sort_order == 'desc':
                    query = query.order_by(Ticket.subject.desc())
                else:
                    query = query.order_by(Ticket.subject.asc())
            elif sort_by == 'sender':
                if sort_order == 'desc':
                    query = query.order_by(Ticket.sender_name.desc())
                else:
                    query = query.order_by(Ticket.sender_name.asc())
            elif sort_by == 'status':
                if sort_order == 'desc':
                    query = query.order_by(Ticket.status.desc())
                else:
                    query = query.order_by(Ticket.status.asc())

            # Paginate results
            tickets = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )

            return tickets

        except Exception as e:
            logger.error(f"Failed to get tickets: {str(e)}")
            raise

    @staticmethod
    def get_ticket_by_id(ticket_id):
        """Get ticket by ID with attachments"""
        try:
            ticket = Ticket.query.get(ticket_id)
            if not ticket:
                return None

            return ticket

        except Exception as e:
            logger.error(f"Failed to get ticket {ticket_id}: {str(e)}")
            raise

    @staticmethod
    def update_ticket_status(ticket_id, new_status):
        """Update ticket status"""
        try:
            ticket = Ticket.query.get(ticket_id)
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")

            if new_status not in ['new', 'read', 'archived']:
                raise ValueError(f"Invalid status: {new_status}")

            old_status = ticket.status
            ticket.status = new_status
            ticket.updated_at = datetime.utcnow()

            db.session.commit()

            logger.info(f"Updated ticket {ticket.ticket_number} status from {old_status} to {new_status}")
            return ticket

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update ticket {ticket_id} status: {str(e)}")
            raise

    @staticmethod
    def mark_as_read(ticket_id):
        """Mark ticket as read"""
        return TicketService.update_ticket_status(ticket_id, 'read')

    @staticmethod
    def mark_as_unread(ticket_id):
        """Mark ticket as unread (new)"""
        return TicketService.update_ticket_status(ticket_id, 'new')

    @staticmethod
    def archive_ticket(ticket_id):
        """Archive ticket"""
        return TicketService.update_ticket_status(ticket_id, 'archived')

    @staticmethod
    def bulk_update_status(ticket_ids, new_status):
        """Update status for multiple tickets"""
        try:
            if new_status not in ['new', 'read', 'archived']:
                raise ValueError(f"Invalid status: {new_status}")

            updated_count = 0
            for ticket_id in ticket_ids:
                try:
                    ticket = Ticket.query.get(ticket_id)
                    if ticket:
                        ticket.status = new_status
                        ticket.updated_at = datetime.utcnow()
                        updated_count += 1
                except Exception as e:
                    logger.warning(f"Failed to update ticket {ticket_id}: {str(e)}")

            db.session.commit()
            logger.info(f"Bulk updated {updated_count} tickets to status {new_status}")
            return updated_count

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to bulk update tickets: {str(e)}")
            raise

    @staticmethod
    def delete_ticket(ticket_id):
        """Delete ticket and its attachments"""
        try:
            ticket = Ticket.query.get(ticket_id)
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")

            # Delete attachment files
            for attachment in ticket.attachments:
                try:
                    import os
                    if os.path.exists(attachment.storage_path):
                        os.remove(attachment.storage_path)
                        logger.info(f"Deleted attachment file: {attachment.storage_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete attachment file {attachment.storage_path}: {str(e)}")

            # Delete ticket (cascade will handle attachments)
            ticket_number = ticket.ticket_number
            db.session.delete(ticket)
            db.session.commit()

            logger.info(f"Deleted ticket {ticket_number}")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete ticket {ticket_id}: {str(e)}")
            raise

    @staticmethod
    def get_ticket_stats():
        """Get ticket statistics"""
        try:
            stats = {
                'total': Ticket.query.count(),
                'new': Ticket.query.filter_by(status='new').count(),
                'read': Ticket.query.filter_by(status='read').count(),
                'archived': Ticket.query.filter_by(status='archived').count()
            }

            # Recent activity (last 24 hours)
            from datetime import timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            stats['recent'] = Ticket.query.filter(Ticket.created_at >= yesterday).count()

            return stats

        except Exception as e:
            logger.error(f"Failed to get ticket stats: {str(e)}")
            raise

    @staticmethod
    def search_tickets(query, page=1, per_page=20):
        """Advanced search for tickets"""
        try:
            search_query = Ticket.query

            # Parse search query for advanced features
            if ':' in query:
                # Support search operators like status:new, from:user@example.com
                parts = query.split()
                filters = []
                text_parts = []

                for part in parts:
                    if ':' in part:
                        key, value = part.split(':', 1)
                        key = key.lower()

                        if key == 'status':
                            filters.append(Ticket.status == value)
                        elif key == 'from':
                            filters.append(or_(
                                Ticket.sender_email.contains(value),
                                Ticket.sender_name.contains(value)
                            ))
                        elif key == 'subject':
                            filters.append(Ticket.subject.contains(value))
                        elif key == 'priority':
                            try:
                                priority = int(value)
                                filters.append(Ticket.priority == priority)
                            except ValueError:
                                pass
                    else:
                        text_parts.append(part)

                # Apply filters
                for filter_condition in filters:
                    search_query = search_query.filter(filter_condition)

                # Apply text search to remaining parts
                if text_parts:
                    text_search = ' '.join(text_parts)
                    search_query = search_query.filter(or_(
                        Ticket.subject.contains(text_search),
                        Ticket.content_text.contains(text_search),
                        Ticket.sender_name.contains(text_search),
                        Ticket.sender_email.contains(text_search)
                    ))
            else:
                # Simple text search
                search_query = search_query.filter(or_(
                    Ticket.subject.contains(query),
                    Ticket.content_text.contains(query),
                    Ticket.sender_name.contains(query),
                    Ticket.sender_email.contains(query)
                ))

            # Order by relevance (could be enhanced with full-text search)
            search_query = search_query.order_by(Ticket.received_at.desc())

            # Paginate
            results = search_query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )

            return results

        except Exception as e:
            logger.error(f"Failed to search tickets: {str(e)}")
            raise

    @staticmethod
    def get_sync_status():
        """Get last sync status and statistics"""
        try:
            last_sync = EmailSyncLog.query.order_by(EmailSyncLog.sync_time.desc()).first()
            recent_syncs = EmailSyncLog.query.order_by(EmailSyncLog.sync_time.desc()).limit(10).all()

            sync_stats = {
                'total_syncs': EmailSyncLog.query.count(),
                'successful_syncs': EmailSyncLog.query.filter_by(status='success').count(),
                'failed_syncs': EmailSyncLog.query.filter_by(status='failure').count()
            }

            return {
                'last_sync': last_sync,
                'recent_syncs': recent_syncs,
                'stats': sync_stats
            }

        except Exception as e:
            logger.error(f"Failed to get sync status: {str(e)}")
            raise

    @staticmethod
    def cleanup_old_data(days_to_keep=90):
        """Clean up old tickets and attachments"""
        try:
            from datetime import timedelta
            import os

            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            # Find old archived tickets
            old_tickets = Ticket.query.filter(
                and_(
                    Ticket.status == 'archived',
                    Ticket.updated_at < cutoff_date
                )
            ).all()

            deleted_count = 0
            for ticket in old_tickets:
                # Delete attachment files
                for attachment in ticket.attachments:
                    try:
                        if os.path.exists(attachment.storage_path):
                            os.remove(attachment.storage_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete attachment file: {str(e)}")

                # Delete ticket
                db.session.delete(ticket)
                deleted_count += 1

            db.session.commit()
            logger.info(f"Cleaned up {deleted_count} old tickets")

            return deleted_count

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to cleanup old data: {str(e)}")
            raise