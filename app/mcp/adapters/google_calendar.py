import httpx
from app.mcp.base import BaseMCPTool
from app.mcp.registry import register_tool

CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class CalendarListEvents(BaseMCPTool):
    name = "google_calendar.list_events"
    description = "List upcoming events from the user's Google Calendar."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "max_results": {"type": "integer", "default": 10},
            "time_min": {"type": "string", "description": "ISO 8601 datetime to filter events after"},
        },
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        from datetime import datetime, timezone
        query = {
            "maxResults": params.get("max_results", 10),
            "singleEvents": True,
            "orderBy": "startTime",
            "timeMin": params.get("time_min", datetime.now(timezone.utc).isoformat()),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CALENDAR_API}/calendars/primary/events",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params=query,
            )
            resp.raise_for_status()
            events = resp.json().get("items", [])
            return {"events": [{"id": e["id"], "summary": e.get("summary"), "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date")), "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date")), "location": e.get("location")} for e in events]}


class CalendarCreateEvent(BaseMCPTool):
    name = "google_calendar.create_event"
    description = "Create a new event on the user's Google Calendar."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Event title"},
            "start_time": {"type": "string", "description": "ISO 8601 start datetime"},
            "end_time": {"type": "string", "description": "ISO 8601 end datetime"},
            "description": {"type": "string"},
            "location": {"type": "string"},
        },
        "required": ["summary", "start_time", "end_time"],
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        event_body = {
            "summary": params["summary"],
            "start": {"dateTime": params["start_time"]},
            "end": {"dateTime": params["end_time"]},
        }
        if params.get("description"):
            event_body["description"] = params["description"]
        if params.get("location"):
            event_body["location"] = params["location"]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CALENDAR_API}/calendars/primary/events",
                headers={"Authorization": f"Bearer {oauth_token}", "Content-Type": "application/json"},
                json=event_body,
            )
            resp.raise_for_status()
            event = resp.json()
            return {"event_id": event["id"], "url": event.get("htmlLink"), "summary": event["summary"]}


def register_tools():
    for tool_cls in [CalendarListEvents, CalendarCreateEvent]:
        register_tool(tool_cls())
