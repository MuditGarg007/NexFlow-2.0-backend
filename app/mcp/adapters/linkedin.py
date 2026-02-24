import httpx
from app.mcp.base import BaseMCPTool
from app.mcp.registry import register_tool

LINKEDIN_API = "https://api.linkedin.com/v2"


class LinkedInGetProfile(BaseMCPTool):
    name = "linkedin.get_profile"
    description = "Get the authenticated user's LinkedIn profile information."
    integration_id = "linkedin"
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, params: dict, oauth_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{LINKEDIN_API}/userinfo",
                headers={"Authorization": f"Bearer {oauth_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {"name": data.get("name"), "email": data.get("email"), "picture": data.get("picture"), "locale": data.get("locale")}


class LinkedInCreatePost(BaseMCPTool):
    name = "linkedin.create_post"
    description = "Create a text post on the user's LinkedIn feed."
    integration_id = "linkedin"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Post content text"},
        },
        "required": ["text"],
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        # first get the user's person URN
        async with httpx.AsyncClient() as client:
            me = await client.get(f"{LINKEDIN_API}/userinfo", headers={"Authorization": f"Bearer {oauth_token}"})
            me.raise_for_status()
            person_id = me.json().get("sub")

            post_body = {
                "author": f"urn:li:person:{person_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": params["text"]},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
            resp = await client.post(
                f"{LINKEDIN_API}/ugcPosts",
                headers={"Authorization": f"Bearer {oauth_token}", "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"},
                json=post_body,
            )
            resp.raise_for_status()
            return {"post_id": resp.json().get("id"), "status": "published"}


def register_tools():
    for tool_cls in [LinkedInGetProfile, LinkedInCreatePost]:
        register_tool(tool_cls())
