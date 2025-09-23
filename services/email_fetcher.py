import imaplib
import email
import logging
import time
import os
import hashlib
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import decode_header
from database.models import db, Ticket, Attachment, EmailSyncLog, Settings

logger = logging.getLogger(__name__)

class EmailFetcher:
    """Service for fetching emails from IMAP server and converting to tickets"""

    def __init__(self, config=None):
        # Use database settings if available, fallback to config for critical settings only
        self.config = config or {}
        self._settings_loaded = False

    def _load_settings(self):
        """Load settings from database"""
        self.imap_server = Settings.get('IMAP_SERVER', 'imap.gmail.com')
        self.imap_port = int(Settings.get('IMAP_PORT', 993))
        self.username = Settings.get('IMAP_USERNAME', '')
        self.password = Settings.get('IMAP_PASSWORD', '')
        self.use_ssl = Settings.get('IMAP_USE_SSL', 'true').lower() == 'true'
        self.folder = Settings.get('IMAP_FOLDER', 'INBOX')
        self.max_emails = int(Settings.get('MAX_EMAILS_PER_SYNC', 50))
        self.attachment_storage = Settings.get('ATTACHMENT_STORAGE_PATH', 'storage/attachments')

        # Ensure attachment directory exists
        os.makedirs(self.attachment_storage, exist_ok=True)
        self._settings_loaded = True

    def _ensure_settings_loaded(self):
        """Ensure settings are loaded before use"""
        if not self._settings_loaded:
            self._load_settings()

    def refresh_settings(self):
        """Refresh settings from database"""
        self._load_settings()

    def connect(self):
        """Connect to IMAP server"""
        self._ensure_settings_loaded()
        try:
            if self.use_ssl:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                mail = imaplib.IMAP4(self.imap_server, self.imap_port)

            mail.login(self.username, self.password)
            logger.info(f"Connected to IMAP server: {self.imap_server}")
            return mail

        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {str(e)}")
            raise

    def test_connection(self):
        """Test IMAP connection and return status"""
        self._ensure_settings_loaded()
        try:
            mail = self.connect()
            mail.select(self.folder)
            mail.logout()
            return {'status': 'success', 'message': 'Connection successful'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def decode_mime_words(self, s):
        """Decode MIME encoded words in headers"""
        if not s:
            return ""

        decoded_words = decode_header(s)
        decoded_string = ""

        for word, encoding in decoded_words:
            if isinstance(word, bytes):
                if encoding:
                    try:
                        decoded_string += word.decode(encoding)
                    except (UnicodeDecodeError, LookupError):
                        decoded_string += word.decode('utf-8', errors='ignore')
                else:
                    decoded_string += word.decode('utf-8', errors='ignore')
            else:
                decoded_string += word

        return decoded_string

    def extract_email_content(self, msg):
        """Extract text and HTML content from email message"""
        text_content = ""
        html_content = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            text_content += payload.decode('utf-8', errors='ignore')
                    except Exception as e:
                        logger.warning(f"Failed to decode text content: {str(e)}")

                elif content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            html_content += payload.decode('utf-8', errors='ignore')
                    except Exception as e:
                        logger.warning(f"Failed to decode HTML content: {str(e)}")
        else:
            # Not multipart
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    content = payload.decode('utf-8', errors='ignore')
                    if content_type == "text/html":
                        html_content = content
                    else:
                        text_content = content
            except Exception as e:
                logger.warning(f"Failed to decode message content: {str(e)}")

        return text_content.strip(), html_content.strip()

    def save_attachment(self, part, ticket_id, filename):
        """Save email attachment to disk"""
        self._ensure_settings_loaded()
        try:
            # Sanitize filename
            filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
            if not filename:
                filename = f"attachment_{int(time.time())}"

            # Create unique filename to avoid conflicts
            timestamp = str(int(time.time()))
            safe_filename = f"{ticket_id}_{timestamp}_{filename}"
            file_path = os.path.join(self.attachment_storage, safe_filename)

            # Get attachment data
            payload = part.get_payload(decode=True)
            if not payload:
                logger.warning(f"Empty attachment payload for {filename}")
                return None

            # Calculate file size and checksum
            file_size = len(payload)
            checksum = hashlib.md5(payload).hexdigest()

            # Check file size limit
            max_size = int(Settings.get('ATTACHMENT_MAX_SIZE', 10485760))  # 10MB
            if file_size > max_size:
                logger.warning(f"Attachment {filename} exceeds size limit ({file_size} > {max_size})")
                return None

            # Save file
            with open(file_path, 'wb') as f:
                f.write(payload)

            # Check if this is an embedded image
            content_id = part.get('Content-ID', '').strip('<>')
            content_disposition = str(part.get("Content-Disposition", ""))
            is_embedded = (content_id and
                          (part.get_content_type().startswith('image/') or
                           'inline' in content_disposition.lower()))

            # Create attachment record
            attachment = Attachment(
                ticket_id=ticket_id,
                filename=filename,
                content_type=part.get_content_type(),
                size=file_size,
                storage_path=file_path,
                checksum=checksum,
                content_id=content_id if content_id else None,
                is_embedded=is_embedded
            )

            db.session.add(attachment)
            logger.info(f"Saved attachment: {filename} ({file_size} bytes)")
            return attachment

        except Exception as e:
            logger.error(f"Failed to save attachment {filename}: {str(e)}")
            return None

    def extract_attachments(self, msg, ticket_id):
        """Extract and save all attachments from email"""
        attachments = []

        if not msg.is_multipart():
            logger.debug(f"Email is not multipart, no attachments expected for ticket {ticket_id}")
            return attachments

        logger.debug(f"Processing multipart email for ticket {ticket_id}")
        part_count = 0

        for part in msg.walk():
            part_count += 1
            content_disposition = str(part.get("Content-Disposition", ""))
            content_id = part.get('Content-ID', '')
            content_type = part.get_content_type()

            logger.debug(f"Part {part_count}: Type={content_type}, Disposition='{content_disposition}', CID='{content_id}'")

            # Process attachments and embedded images
            # Check for explicit attachment/inline disposition
            has_attachment_disposition = ("attachment" in content_disposition.lower() or
                                        "inline" in content_disposition.lower())

            # Check for embedded images with CID
            is_embedded_image = (content_id and content_type.startswith('image/'))

            # Check for files with filenames (even without explicit disposition)
            filename = part.get_filename()
            has_filename = bool(filename)

            # Skip text/html and text/plain parts unless they have explicit disposition
            is_content_part = content_type in ['text/plain', 'text/html', 'multipart/alternative', 'multipart/related', 'multipart/mixed']

            should_process = (has_attachment_disposition or
                            is_embedded_image or
                            (has_filename and not is_content_part))

            if should_process:
                logger.debug(f"Part {part_count} identified as attachment: filename='{filename}', disposition='{content_disposition}', type='{content_type}'")

                if filename:
                    filename = self.decode_mime_words(filename)
                elif content_id:
                    # Generate filename for embedded image without explicit filename
                    ext = content_type.split('/')[-1]
                    filename = f"embedded_image_{content_id.strip('<>')}.{ext}"
                    logger.debug(f"Generated filename for embedded image: {filename}")
                else:
                    logger.debug(f"Part {part_count} skipped: no filename and no content ID")
                    continue

                attachment = self.save_attachment(part, ticket_id, filename)
                if attachment:
                    attachments.append(attachment)
                    logger.info(f"Successfully saved attachment: {filename}")
                else:
                    logger.warning(f"Failed to save attachment: {filename}")

        logger.info(f"Extracted {len(attachments)} attachments from email for ticket {ticket_id}")
        return attachments

    def process_html_content(self, html_content, attachments):
        """Process HTML content to replace CID references with attachment URLs"""
        if not html_content or not attachments:
            return html_content

        # Create mapping of Content-ID to attachment ID
        cid_to_attachment = {}
        for attachment in attachments:
            if attachment.content_id and attachment.is_embedded:
                # Handle both <cid> and cid formats
                clean_cid = attachment.content_id.strip('<>')
                cid_to_attachment[clean_cid] = attachment.id

        # Replace cid: references in HTML
        def replace_cid(match):
            cid = match.group(1)
            if cid in cid_to_attachment:
                attachment_id = cid_to_attachment[cid]
                return f'src="/attachment/{attachment_id}"'
            return match.group(0)  # Return original if no mapping found

        # Pattern to match src="cid:..." references
        cid_pattern = r'src=["\']cid:([^"\']+)["\']'
        processed_html = re.sub(cid_pattern, replace_cid, html_content, flags=re.IGNORECASE)

        return processed_html

    def parse_email_addresses(self, header_value):
        """Parse email addresses from header value"""
        if not header_value:
            return []

        try:
            addresses = []
            # Simple parsing - could be enhanced with email.utils.parseaddr
            for addr in header_value.split(','):
                addr = addr.strip()
                if addr:
                    addresses.append(addr)
            return addresses
        except Exception as e:
            logger.warning(f"Failed to parse email addresses from '{header_value}': {str(e)}")
            return []

    def message_to_ticket(self, msg, message_id):
        """Convert email message to ticket"""
        try:
            # Extract basic headers
            subject = self.decode_mime_words(msg.get('Subject', 'No Subject'))
            from_header = self.decode_mime_words(msg.get('From', ''))
            to_header = self.decode_mime_words(msg.get('To', ''))
            cc_header = self.decode_mime_words(msg.get('Cc', ''))
            date_header = msg.get('Date', '')

            # Parse sender information
            sender_email = from_header
            sender_name = ""

            # Extract email and name from "Name <email>" format
            if '<' in from_header and '>' in from_header:
                name_part = from_header.split('<')[0].strip().strip('"')
                email_part = from_header.split('<')[1].split('>')[0].strip()
                sender_name = name_part
                sender_email = email_part
            elif '@' in from_header:
                sender_email = from_header.strip()

            # Parse received date
            received_at = datetime.utcnow()
            if date_header:
                try:
                    received_at = email.utils.parsedate_to_datetime(date_header)
                    # Convert to UTC if timezone-aware
                    if received_at.tzinfo:
                        received_at = received_at.utctimetuple()
                        received_at = datetime(*received_at[:6])
                except Exception as e:
                    logger.warning(f"Failed to parse date '{date_header}': {str(e)}")

            # Extract content
            text_content, html_content = self.extract_email_content(msg)

            # Parse CC emails
            cc_emails = self.parse_email_addresses(cc_header) if cc_header else []

            # Prepare raw headers
            raw_headers = {}
            for key, value in msg.items():
                raw_headers[key] = self.decode_mime_words(value)

            # Create ticket
            ticket = Ticket(
                ticket_number=Ticket.create_unique_ticket_number(),
                source='email',
                source_id=message_id,
                subject=subject,
                content_text=text_content,
                content_html=html_content,
                sender_email=sender_email,
                sender_name=sender_name,
                recipient_email=to_header,
                received_at=received_at,
                status='new'
            )

            # Set JSON fields
            ticket.set_cc_emails(cc_emails)
            ticket.set_raw_headers(raw_headers)

            # Save ticket to get ID for attachments
            db.session.add(ticket)
            db.session.flush()  # Get the ID without committing

            # Extract attachments
            attachments = self.extract_attachments(msg, ticket.id)

            # Process HTML content to replace CID references with attachment URLs
            if html_content and attachments:
                processed_html = self.process_html_content(html_content, attachments)
                ticket.content_html = processed_html

            logger.info(f"Created ticket {ticket.ticket_number} from email: {subject}")
            return ticket

        except Exception as e:
            logger.error(f"Failed to convert email to ticket: {str(e)}")
            raise

    def fetch_new_emails(self):
        """Fetch new emails and convert to tickets"""
        self._ensure_settings_loaded()
        start_time = time.time()
        emails_fetched = 0
        last_uid = None

        try:
            mail = self.connect()
            mail.select(self.folder)

            # Search for emails
            # For first sync, get recent emails. For subsequent syncs, get since last UID
            last_sync_uid = EmailSyncLog.get_last_uid()

            if last_sync_uid:
                # Get emails since last UID
                search_criteria = f'UID {last_sync_uid}:*'
            else:
                # First sync - get recent emails (limit by count)
                search_criteria = 'ALL'

            status, messages = mail.search(None, search_criteria)

            if status != 'OK':
                raise Exception(f"IMAP search failed: {status}")

            email_ids = messages[0].split()

            # Limit emails per sync
            if len(email_ids) > self.max_emails:
                email_ids = email_ids[-self.max_emails:]  # Get most recent

            logger.info(f"Found {len(email_ids)} emails to process")

            processed_message_ids = set()

            for email_id in email_ids:
                try:
                    # Fetch email using PEEK to avoid marking as read
                    status, msg_data = mail.fetch(email_id, '(BODY.PEEK[])')
                    if status != 'OK':
                        logger.warning(f"Failed to fetch email {email_id}")
                        continue

                    # Parse email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Get message ID
                    message_id = msg.get('Message-ID', '')
                    if not message_id:
                        message_id = f"no-id-{email_id.decode()}-{int(time.time())}"

                    # Skip if we've already processed this message ID
                    if message_id in processed_message_ids:
                        continue

                    # Check if ticket already exists
                    existing_ticket = Ticket.query.filter_by(source_id=message_id).first()
                    if existing_ticket:
                        logger.debug(f"Ticket already exists for message ID: {message_id}")
                        continue

                    # Convert to ticket
                    ticket = self.message_to_ticket(msg, message_id)
                    processed_message_ids.add(message_id)
                    emails_fetched += 1
                    last_uid = email_id.decode()

                    logger.info(f"Processed email {emails_fetched}: {ticket.subject}")

                except Exception as e:
                    logger.error(f"Failed to process email {email_id}: {str(e)}")
                    continue

            # Commit all changes
            db.session.commit()

            # Close connection
            mail.logout()

            # Calculate duration
            duration = time.time() - start_time

            # Log successful sync
            EmailSyncLog.log_sync(
                emails_fetched=emails_fetched,
                status='success',
                last_uid=last_uid,
                duration=duration
            )

            logger.info(f"Email sync completed: {emails_fetched} emails fetched in {duration:.2f}s")

            return {
                'emails_fetched': emails_fetched,
                'duration': duration,
                'status': 'success'
            }

        except Exception as e:
            # Rollback database changes
            db.session.rollback()

            # Log failed sync
            EmailSyncLog.log_sync(
                emails_fetched=emails_fetched,
                status='failure',
                error_message=str(e),
                duration=time.time() - start_time
            )

            logger.error(f"Email sync failed: {str(e)}")
            raise

    def get_folder_list(self):
        """Get list of available IMAP folders"""
        try:
            mail = self.connect()
            status, folders = mail.list()
            mail.logout()

            if status == 'OK':
                folder_list = []
                for folder in folders:
                    folder_name = folder.decode().split('"')[-2]
                    folder_list.append(folder_name)
                return folder_list
            else:
                raise Exception(f"Failed to get folder list: {status}")

        except Exception as e:
            logger.error(f"Failed to get folder list: {str(e)}")
            raise