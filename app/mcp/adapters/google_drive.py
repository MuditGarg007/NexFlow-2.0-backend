import httpx
from app.mcp.base import BaseMCPTool
from app.mcp.registry import register_tool

DRIVE_API = "https://www.googleapis.com/drive/v3"


class DriveListFiles(BaseMCPTool):
    name = "google_drive.list_files"
    description = "List files from the user's Google Drive."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "page_size": {"type": "integer", "default": 10},
            "query": {"type": "string", "description": "Drive search query"},
        },
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        query_params = {
            "pageSize": params.get("page_size", 10),
            "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
        }
        if params.get("query"):
            query_params["q"] = params["query"]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{DRIVE_API}/files",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params=query_params,
            )
            resp.raise_for_status()
            files = resp.json().get("files", [])
            return {"files": [{"id": f["id"], "name": f["name"], "type": f["mimeType"], "modified": f.get("modifiedTime"), "url": f.get("webViewLink")} for f in files]}


class DriveSearchFiles(BaseMCPTool):
    name = "google_drive.search_files"
    description = "Search for files in Google Drive by name or content."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "search_term": {"type": "string", "description": "Search term to find files"},
            "file_type": {"type": "string", "description": "MIME type filter (e.g. application/pdf)"},
        },
        "required": ["search_term"],
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        q = f"name contains '{params['search_term']}'"
        if params.get("file_type"):
            q += f" and mimeType='{params['file_type']}'"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{DRIVE_API}/files",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params={"q": q, "fields": "files(id,name,mimeType,webViewLink)", "pageSize": 10},
            )
            resp.raise_for_status()
            return {"files": resp.json().get("files", [])}


def register_tools():
    for tool_cls in [DriveListFiles, DriveSearchFiles]:
        register_tool(tool_cls())
