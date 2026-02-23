"""
Node handler registry and implementations.
Focused on the Email → OpenAI Summary → Google Sheets demo workflow.
All API keys and configuration are passed through node data fields.
"""

import json
import base64
import re
import httpx
from abc import ABC, abstractmethod
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.expression import interpolate


class BaseNodeHandler(ABC):
    @abstractmethod
    async def execute(self, data: dict, context: dict, db: AsyncSession) -> dict:
        """Execute the node and return result dict with 'output' key."""
        pass


# ─── Email Trigger ────────────────────────────────────────────────────────────
class EmailTriggerNodeHandler(BaseNodeHandler):
    """
    Receives email data from a webhook payload or manual test input.
    Outputs: subject, body, sender, attachments, received_at.
    """
    async def execute(self, data: dict, context: dict, db: AsyncSession) -> dict:
        trigger = context.get("trigger", {})
        trigger_body = trigger.get("body", {})

        # Gmail poller wraps payload as: {"trigger_type": "gmail", "body": {...}, "integration_id": ...}
        # The executor stores that whole dict as context["trigger"]["body"], so unwrap one level.
        if isinstance(trigger_body, dict) and "body" in trigger_body and isinstance(trigger_body.get("body"), dict):
            trigger_body = trigger_body["body"]

        subject = trigger_body.get("subject") or data.get("test_subject", "(No Subject)")
        body = trigger_body.get("body") or data.get("test_body", "(No Body)")
        sender = trigger_body.get("sender") or data.get("test_sender", "unknown@example.com")
        attachments = trigger_body.get("attachments") or []
        received_at = trigger_body.get("received_at") or ""

        return {
            "output": {
                "subject": subject,
                "body": body,
                "sender": sender,
                "attachments": attachments,
                "received_at": received_at,
                "raw": trigger_body,
            }
        }


# ─── Extract Content ─────────────────────────────────────────────────────────
class ExtractContentNodeHandler(BaseNodeHandler):
    """
    Extracts and normalises all content from the email:
    - Strips HTML tags from body
    - Decodes base64 attachment content (if provided)
    - Combines everything into a single text block for the LLM
    """
    async def execute(self, data: dict, context: dict, db: AsyncSession) -> dict:
        subject = str(data.get("subject", ""))
        body = str(data.get("body", ""))
        attachments = data.get("attachments", [])

        # Strip HTML tags
        clean_body = re.sub(r"<[^>]+>", " ", body)
        clean_body = re.sub(r"\s+", " ", clean_body).strip()

        # Extract attachment text
        attachment_texts = []
        if isinstance(attachments, list):
            for att in attachments:
                if isinstance(att, dict):
                    name = att.get("filename", att.get("name", "attachment"))
                    content = att.get("content", "")
                    if content:
                        try:
                            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
                            attachment_texts.append(f"[Attachment: {name}]\n{decoded}")
                        except Exception:
                            attachment_texts.append(f"[Attachment: {name}] (binary, not decoded)")
                    else:
                        attachment_texts.append(f"[Attachment: {name}]")

        combined = f"Subject: {subject}\n\nBody:\n{clean_body}"
        if attachment_texts:
            combined += "\n\nAttachments:\n" + "\n\n".join(attachment_texts)

        return {
            "output": {
                "subject": subject,
                "clean_body": clean_body,
                "attachment_count": len(attachments) if isinstance(attachments, list) else 0,
                "attachment_texts": attachment_texts,
                "combined_text": combined,
            }
        }


# ─── OpenAI Summarize ─────────────────────────────────────────────────────────
class SummarizeNodeHandler(BaseNodeHandler):
    """
    Sends extracted email content to OpenAI and returns a clean structured summary.
    API key is configured directly in the node — no env file needed.
    """
    async def execute(self, data: dict, context: dict, db: AsyncSession) -> dict:
        from openai import AsyncOpenAI
        from app.config import get_settings

        api_key = data.get("api_key", "").strip()
        if not api_key:
            settings = get_settings()
            api_key = settings.OPENAI_API_KEY

        if not api_key:
            raise ValueError("OpenAI API key is required. Set it in the Summarize node config.")

        client = AsyncOpenAI(api_key=api_key)
        model = data.get("model", "gpt-4o")
        temperature = float(data.get("temperature", 0.3))
        email_content = str(data.get("email_content", ""))

        system_prompt = data.get("system_prompt") or (
            "You are an expert email analyst. Given an email (subject, body, and any attachments), "
            "produce a clean, structured summary with the following sections:\n"
            "1. **Summary** – 2-3 sentence overview\n"
            "2. **Key Points** – bullet list of important information\n"
            "3. **Action Items** – any tasks or follow-ups required\n"
            "4. **Sentiment** – overall tone (positive / neutral / negative)\n"
            "5. **Category** – classify as: support / sales / invoice / hr / general\n"
            "Be concise and professional."
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyse this email:\n\n{email_content}"},
            ],
            temperature=temperature,
        )

        choice = response.choices[0]
        usage = response.usage
        summary_text = choice.message.content or ""

        # Parse structured fields from the summary
        def extract_section(text: str, heading: str) -> str:
            pattern = rf"(?:#+\s*|\*\*)?{re.escape(heading)}[:\*]*\*?\s*([\s\S]*?)(?=\n(?:#+|\d+\.|\*\*)|$)"
            m = re.search(pattern, text, re.IGNORECASE)
            return m.group(1).strip() if m else ""

        return {
            "output": {
                "summary": summary_text,
                "overview": extract_section(summary_text, "Summary"),
                "key_points": extract_section(summary_text, "Key Points"),
                "action_items": extract_section(summary_text, "Action Items"),
                "sentiment": extract_section(summary_text, "Sentiment"),
                "category": extract_section(summary_text, "Category"),
                "model": model,
            },
            "token_usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            } if usage else None,
        }


# ─── Google Sheets ────────────────────────────────────────────────────────────
class GoogleSheetsNodeHandler(BaseNodeHandler):
    """
    Appends a row to a Google Sheet.
    Auth priority:
      1. service_account_json  → uses google-api-python-client (most reliable)
      2. bearer_token          → direct OAuth2 bearer token
    """
    async def execute(self, data: dict, context: dict, db: AsyncSession) -> dict:
        import asyncio
        spreadsheet_id = data.get("spreadsheet_id", "").strip()
        sheet_name = data.get("sheet_name", "Sheet1").strip() or "Sheet1"
        bearer_token = data.get("bearer_token", "").strip()
        service_account_json = data.get("service_account_json", "").strip()

        if not spreadsheet_id:
            raise ValueError("Google Sheets: spreadsheet_id is required.")

        # Build the row values
        row_template = data.get("row_values", [])
        if isinstance(row_template, str):
            try:
                row_template = json.loads(row_template)
            except Exception:
                row_template = [row_template]

        values = [str(v) for v in row_template] if row_template else [
            str(data.get("col_subject", "")),
            str(data.get("col_sender", "")),
            str(data.get("col_summary", "")),
            str(data.get("col_category", "")),
            str(data.get("col_sentiment", "")),
            str(data.get("col_action_items", "")),
            str(data.get("col_received_at", "")),
        ]

        if not service_account_json and not bearer_token:
            raise ValueError(
                "Google Sheets: provide either a service_account_json or bearer_token in the node config."
            )

        # Use google-api-python-client with service account (preferred)
        if service_account_json:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                _append_with_service_account,
                service_account_json,
                spreadsheet_id,
                sheet_name,
                values,
            )
            return result

        # Fallback: raw bearer token via httpx
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            f"/values/{sheet_name}!A1:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        )
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }
        body = {"values": [values]}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=body)

        try:
            resp_data = response.json()
        except Exception:
            resp_data = {"raw": response.text}

        if response.status_code not in (200, 201):
            raise ValueError(f"Google Sheets API error {response.status_code}: {resp_data}")

        return {
            "output": {
                "status": "appended",
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "row_values": values,
                "updated_range": resp_data.get("updates", {}).get("updatedRange", ""),
                "updated_rows": resp_data.get("updates", {}).get("updatedRows", 1),
            }
        }


def _append_with_service_account(
    service_account_json: str,
    spreadsheet_id: str,
    sheet_name: str,
    values: list,
) -> dict:
    """Synchronous helper — runs in executor. Uses google-api-python-client."""
    import json as _json
    import tempfile
    import os

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "google-api-python-client is required. Run: pip install google-api-python-client google-auth"
        )

    # Parse and validate JSON
    try:
        sa_info = _json.loads(service_account_json)
    except Exception:
        raise ValueError("service_account_json is not valid JSON.")

    # Build credentials from dict
    creds = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )

    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    body = {"values": [values]}
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        )
        .execute()
    )

    updates = result.get("updates", {})
    return {
        "output": {
            "status": "appended",
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "row_values": values,
            "updated_range": updates.get("updatedRange", ""),
            "updated_rows": updates.get("updatedRows", 1),
        }
    }


# ─── Response Node ────────────────────────────────────────────────────────────
class ResponseNodeHandler(BaseNodeHandler):
    """Final output node — formats and returns the workflow result."""
    async def execute(self, data: dict, context: dict, db: AsyncSession) -> dict:
        body = data.get("body", {})
        return {
            "output": {
                "type": "json",
                "data": body,
            }
        }


# ─── Handler Registry ─────────────────────────────────────────────────────────
_HANDLERS: dict[str, type[BaseNodeHandler]] = {
    "email_trigger": EmailTriggerNodeHandler,
    "extract_content": ExtractContentNodeHandler,
    "summarize": SummarizeNodeHandler,
    "google_sheets": GoogleSheetsNodeHandler,
    "response": ResponseNodeHandler,
}


def get_node_handler(node_type: str, custom_definition: dict | None = None) -> BaseNodeHandler:
    handler_class = _HANDLERS.get(node_type)
    if not handler_class:
        raise ValueError(f"Unknown node type: '{node_type}'. Supported: {list(_HANDLERS.keys())}")
    return handler_class()
