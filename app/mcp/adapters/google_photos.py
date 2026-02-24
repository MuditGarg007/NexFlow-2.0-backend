import httpx
from app.mcp.base import BaseMCPTool
from app.mcp.registry import register_tool

PHOTOS_API = "https://photoslibrary.googleapis.com/v1"


class PhotosListAlbums(BaseMCPTool):
    name = "google_photos.list_albums"
    description = "List photo albums from the user's Google Photos."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "page_size": {"type": "integer", "default": 10},
        },
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{PHOTOS_API}/albums",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params={"pageSize": params.get("page_size", 10)},
            )
            resp.raise_for_status()
            albums = resp.json().get("albums", [])
            return {"albums": [{"id": a["id"], "title": a.get("title"), "item_count": a.get("mediaItemsCount"), "url": a.get("productUrl")} for a in albums]}


class PhotosSearchPhotos(BaseMCPTool):
    name = "google_photos.search_photos"
    description = "Search for photos in Google Photos by date or content category."
    integration_id = "google"
    input_schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["LANDSCAPES", "RECEIPTS", "CITYSCAPES", "FOOD", "ANIMALS", "SELFIES", "PEOPLE", "PETS", "SCREENSHOTS", "NONE"], "description": "Content category filter"},
            "page_size": {"type": "integer", "default": 10},
        },
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        body = {"pageSize": params.get("page_size", 10)}
        if params.get("category") and params["category"] != "NONE":
            body["filters"] = {"contentFilter": {"includedContentCategories": [params["category"]]}}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{PHOTOS_API}/mediaItems:search",
                headers={"Authorization": f"Bearer {oauth_token}", "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
            items = resp.json().get("mediaItems", [])
            return {"photos": [{"id": i["id"], "filename": i.get("filename"), "url": i.get("productUrl"), "created": i.get("mediaMetadata", {}).get("creationTime")} for i in items]}


def register_tools():
    for tool_cls in [PhotosListAlbums, PhotosSearchPhotos]:
        register_tool(tool_cls())
