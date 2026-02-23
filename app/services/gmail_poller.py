"""
Background polling service for Gmail integrations.
Polls Gmail accounts and triggers workflows when new emails arrive.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.integration import Integration
from app.models.workflow import Workflow
from app.services.gmail_service import GmailService
from app.engine.executor import WorkflowExecutor
from app.utils.encryption import decrypt_credentials


class GmailPoller:
    """Polls Gmail accounts and triggers workflows."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.polling_interval = 60
        self.last_check: Dict[str, datetime] = {}
        self.is_running = False
    
    async def start(self):
        """Start the polling loop."""
        self.is_running = True
        print("Gmail Poller: Started")
        
        while self.is_running:
            try:
                await self._poll_all_gmail_integrations()
            except Exception as e:
                print(f"Gmail Poller error: {e}")
            
            await asyncio.sleep(self.polling_interval)
    
    async def stop(self):
        """Stop the polling loop."""
        self.is_running = False
        print("Gmail Poller: Stopped")
    
    async def _poll_all_gmail_integrations(self):
        """Poll all active Gmail integrations."""
        result = await self.db.execute(
            select(Integration).where(
                Integration.type == "gmail",
                Integration.status == "active"
            )
        )
        integrations = result.scalars().all()
        
        for integration in integrations:
            try:
                await self._poll_integration(integration)
            except Exception as e:
                print(f"Error polling integration {integration.id}: {e}")
    
    async def _poll_integration(self, integration: Integration):
        """Poll a specific Gmail integration."""
        try:
            credentials = decrypt_credentials(integration.credentials_encrypted)
            gmail_service = GmailService(credentials)
            
            integration_key = str(integration.id)
            last_check = self.last_check.get(integration_key)
            
            if last_check:
                messages = gmail_service.get_messages_since(
                    since_datetime=last_check,
                    max_results=50
                )
            else:
                messages = gmail_service.get_unread_messages(max_results=10)
            
            self.last_check[integration_key] = datetime.utcnow()
            
            if messages:
                print(f"Gmail Poller: Found {len(messages)} new messages for integration {integration.id}")
                await self._trigger_workflows(integration, messages)
            
            updated_creds = gmail_service.get_updated_credentials()
            if updated_creds.get("access_token") != credentials.get("access_token"):
                from app.utils.encryption import encrypt_credentials
                integration.credentials_encrypted = encrypt_credentials(updated_creds)
                await self.db.flush()
            
        except Exception as e:
            print(f"Error in _poll_integration for {integration.id}: {e}")
            raise
    
    async def _trigger_workflows(self, integration: Integration, messages: List[Dict]):
        """Trigger workflows for new messages."""
        result = await self.db.execute(
            select(Workflow).where(
                Workflow.user_id == integration.user_id,
                Workflow.status == "published"
            )
        )
        workflows = result.scalars().all()
        
        gmail_workflows = []
        for workflow in workflows:
            nodes = workflow.nodes or []
            for node in nodes:
                # nodes are WorkflowNode ORM objects
                node_type = node.type if hasattr(node, "type") else node.get("type")
                node_data = node.data if hasattr(node, "data") else node.get("data", {})
                if not isinstance(node_data, dict):
                    node_data = {}

                if node_type == "email_trigger":
                    trigger_config = node_data.get("trigger_config", {})
                    if not isinstance(trigger_config, dict):
                        trigger_config = {}
                    if trigger_config.get("integration_id") == str(integration.id):
                        gmail_workflows.append(workflow)
                        break
        
        if not gmail_workflows:
            print(f"No workflows configured for Gmail integration {integration.id}")
            return
        
        executor = WorkflowExecutor(self.db)
        
        for message in messages:
            for workflow in gmail_workflows:
                try:
                    trigger_payload = {
                        "trigger_type": "gmail",
                        "integration_id": str(integration.id),
                        "body": {
                            "message_id": message.get("message_id"),
                            "thread_id": message.get("thread_id"),
                            "subject": message.get("subject"),
                            "sender": message.get("sender"),
                            "to": message.get("to"),
                            "body": message.get("body"),
                            "email_content": message.get("body"),
                            "attachments": message.get("attachments", []),
                            "received_at": message.get("received_at"),
                            "snippet": message.get("snippet"),
                            "labels": message.get("labels", [])
                        }
                    }
                    
                    print(f"Triggering workflow {workflow.id} for email: {message.get('subject')}")
                    await executor.execute(workflow, trigger_payload, trigger_type="gmail")
                    
                except Exception as e:
                    print(f"Error executing workflow {workflow.id}: {e}")


_poller_instance: Optional[GmailPoller] = None


async def start_gmail_poller(db: AsyncSession):
    """Start the global Gmail poller instance."""
    global _poller_instance
    if _poller_instance is None:
        _poller_instance = GmailPoller(db)
        asyncio.create_task(_poller_instance.start())


async def stop_gmail_poller():
    """Stop the global Gmail poller instance."""
    global _poller_instance
    if _poller_instance:
        await _poller_instance.stop()
        _poller_instance = None
