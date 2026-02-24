import httpx
from app.mcp.base import BaseMCPTool
from app.mcp.registry import register_tool

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"


class GmailListEmails(BaseMCPTool):
    name = "gmail.list_emails"
    description = "List recent emails from the user's Gmail inbox."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "max_results": {"type": "integer", "default": 10, "maximum": 50},
            "query": {"type": "string", "description": "Gmail search query (e.g., 'from:user@example.com')"},
        },
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            query_params = {"maxResults": params.get("max_results", 10)}
            if params.get("query"):
                query_params["q"] = params["query"]
            resp = await client.get(
                f"{GMAIL_API}/users/me/messages",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params=query_params,
            )
            resp.raise_for_status()
            message_ids = resp.json().get("messages", [])

            emails = []
            for mid in message_ids[:params.get("max_results", 10)]:
                detail = await client.get(
                    f"{GMAIL_API}/users/me/messages/{mid['id']}",
                    headers={"Authorization": f"Bearer {oauth_token}"},
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
                )
                detail.raise_for_status()
                headers = {h["name"]: h["value"] for h in detail.json().get("payload", {}).get("headers", [])}
                emails.append({"id": mid["id"], "subject": headers.get("Subject"), "from": headers.get("From"), "date": headers.get("Date"), "snippet": detail.json().get("snippet")})
            return {"emails": emails}


class GmailSendEmail(BaseMCPTool):
    name = "gmail.send_email"
    description = "Send an email from the user's Gmail account."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string"},
            "body": {"type": "string", "description": "Plain text email body"},
        },
        "required": ["to", "subject", "body"],
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        import base64
        raw = f"To: {params['to']}\nSubject: {params['subject']}\nContent-Type: text/plain; charset=utf-8\n\n{params['body']}"
        encoded = base64.urlsafe_b64encode(raw.encode()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GMAIL_API}/users/me/messages/send",
                headers={"Authorization": f"Bearer {oauth_token}", "Content-Type": "application/json"},
                json={"raw": encoded},
            )
            resp.raise_for_status()
            return {"message_id": resp.json().get("id"), "status": "sent"}


class GmailReadEmail(BaseMCPTool):
    name = "gmail.read_email"
    description = "Read the full content of a specific email by its message ID."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "Gmail message ID"},
        },
        "required": ["message_id"],
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GMAIL_API}/users/me/messages/{params['message_id']}",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params={"format": "full"},
            )
            resp.raise_for_status()
            data = resp.json()
            headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
            return {"id": data["id"], "subject": headers.get("Subject"), "from": headers.get("From"), "date": headers.get("Date"), "body": data.get("snippet")}


def register_tools():
    for tool_cls in [GmailListEmails, GmailSendEmail, GmailReadEmail]:
        register_tool(tool_cls())
