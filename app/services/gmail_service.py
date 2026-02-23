"""
Gmail service for fetching and processing emails.
Supports OAuth2 authentication and polling for new messages.
"""

import base64
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GmailService:
    """Service for interacting with Gmail API."""
    
    def __init__(self, credentials_dict: dict):
        """
        Initialize Gmail service with OAuth2 credentials.
        
        Args:
            credentials_dict: Dictionary containing OAuth2 credentials
                {
                    "access_token": "...",
                    "refresh_token": "...",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": "...",
                    "client_secret": "...",
                    "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
                }
        """
        self.credentials = Credentials(
            token=credentials_dict.get("access_token"),
            refresh_token=credentials_dict.get("refresh_token"),
            token_uri=credentials_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=credentials_dict.get("client_id"),
            client_secret=credentials_dict.get("client_secret"),
            scopes=credentials_dict.get("scopes", ["https://www.googleapis.com/auth/gmail.readonly"])
        )
        
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
        
        self.service = build('gmail', 'v1', credentials=self.credentials)
    
    def get_unread_messages(self, max_results: int = 10, query: str = "is:unread") -> List[Dict[str, Any]]:
        """
        Fetch unread messages from Gmail.
        
        Args:
            max_results: Maximum number of messages to fetch
            query: Gmail search query (default: unread messages)
            
        Returns:
            List of processed email dictionaries
        """
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            processed_emails = []
            
            for msg in messages:
                email_data = self._get_message_details(msg['id'])
                if email_data:
                    processed_emails.append(email_data)
            
            return processed_emails
            
        except HttpError as error:
            raise Exception(f"Gmail API error: {error}")
    
    def get_messages_since(self, since_datetime: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch messages received since a specific datetime.
        
        Args:
            since_datetime: Fetch messages after this datetime
            max_results: Maximum number of messages to fetch
            
        Returns:
            List of processed email dictionaries
        """
        timestamp = int(since_datetime.timestamp())
        query = f"after:{timestamp}"
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            processed_emails = []
            
            for msg in messages:
                email_data = self._get_message_details(msg['id'])
                if email_data:
                    processed_emails.append(email_data)
            
            return processed_emails
            
        except HttpError as error:
            raise Exception(f"Gmail API error: {error}")
    
    def _get_message_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific message.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Dictionary with email details
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload'].get('headers', [])
            
            subject = self._get_header(headers, 'Subject')
            sender = self._get_header(headers, 'From')
            to = self._get_header(headers, 'To')
            date = self._get_header(headers, 'Date')
            
            body = self._get_message_body(message['payload'])
            attachments = self._get_attachments(message['payload'])
            
            internal_date = message.get('internalDate')
            received_at = datetime.fromtimestamp(int(internal_date) / 1000).isoformat() if internal_date else date
            
            return {
                "message_id": message_id,
                "thread_id": message.get('threadId'),
                "subject": subject or "(No Subject)",
                "sender": sender or "unknown@example.com",
                "to": to or "",
                "body": body,
                "body_html": body,
                "attachments": attachments,
                "received_at": received_at,
                "labels": message.get('labelIds', []),
                "snippet": message.get('snippet', ''),
                "raw_headers": {h['name']: h['value'] for h in headers}
            }
            
        except HttpError as error:
            print(f"Error fetching message {message_id}: {error}")
            return None
    
    def _get_header(self, headers: List[Dict], name: str) -> Optional[str]:
        """Extract a specific header value."""
        for header in headers:
            if header['name'].lower() == name.lower():
                return header['value']
        return None
    
    def _get_message_body(self, payload: Dict) -> str:
        """Extract message body from payload."""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        break
                elif part['mimeType'] == 'text/html' and not body:
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif 'parts' in part:
                    body = self._get_message_body(part)
                    if body:
                        break
        else:
            data = payload['body'].get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        return body
    
    def _get_attachments(self, payload: Dict) -> List[Dict[str, Any]]:
        """Extract attachment information from payload."""
        attachments = []
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    attachment = {
                        "filename": part['filename'],
                        "mime_type": part['mimeType'],
                        "size": part['body'].get('size', 0),
                        "attachment_id": part['body'].get('attachmentId')
                    }
                    attachments.append(attachment)
                elif 'parts' in part:
                    attachments.extend(self._get_attachments(part))
        
        return attachments
    
    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark a message as read.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            True if successful
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            return True
        except HttpError as error:
            print(f"Error marking message as read: {error}")
            return False
    
    def get_updated_credentials(self) -> dict:
        """
        Get updated credentials (in case token was refreshed).
        
        Returns:
            Dictionary with updated credentials
        """
        return {
            "access_token": self.credentials.token,
            "refresh_token": self.credentials.refresh_token,
            "token_uri": self.credentials.token_uri,
            "client_id": self.credentials.client_id,
            "client_secret": self.credentials.client_secret,
            "scopes": self.credentials.scopes,
            "expiry": self.credentials.expiry.isoformat() if self.credentials.expiry else None
        }
