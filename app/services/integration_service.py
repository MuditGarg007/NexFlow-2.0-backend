import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration
from app.models.oauth_connection import OAuthConnection
from app.config import get_settings
from app.redis import redis_client
from app.utils.crypto import encrypt_token, decrypt_token
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

OAUTH_CONFIGS = {
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "client_id_key": "GITHUB_CLIENT_ID",
        "client_secret_key": "GITHUB_CLIENT_SECRET",
        "scopes": ["repo", "user"],
    },
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id_key": "GOOGLE_CLIENT_ID",
        "client_secret_key": "GOOGLE_CLIENT_SECRET",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/photoslibrary.readonly",
            "openid", "email", "profile",
        ],
    },
    "linkedin": {
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "client_id_key": "LINKEDIN_CLIENT_ID",
        "client_secret_key": "LINKEDIN_CLIENT_SECRET",
        "scopes": ["openid", "profile", "email", "w_member_social"],
    },
}


class IntegrationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[Integration]:
        result = await self.db.execute(select(Integration).where(Integration.is_active == True))
        return list(result.scalars().all())

    async def list_connected(self, user_id) -> list[OAuthConnection]:
        result = await self.db.execute(
            select(OAuthConnection).where(OAuthConnection.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_connected_integration_ids(self, user_id) -> list[str]:
        connections = await self.list_connected(user_id)
        return [c.integration_id for c in connections]

    def build_authorize_url(self, integration_id: str, user_id: str) -> str:
        config = OAUTH_CONFIGS.get(integration_id)
        if not config:
            raise ValueError(f"Unknown integration: {integration_id}")

        state = secrets.token_urlsafe(32)
        import asyncio
        asyncio.get_event_loop().create_task(
            redis_client.setex(f"oauth_state:{state}", 600, f"{user_id}:{integration_id}")
        )

        client_id = getattr(settings, config["client_id_key"])
        scopes = " ".join(config["scopes"])
        callback_url = f"{settings.FRONTEND_URL}/api/v1/integrations/{integration_id}/oauth/callback"

        params = {
            "client_id": client_id,
            "redirect_uri": callback_url,
            "scope": scopes,
            "state": state,
            "response_type": "code",
        }
        if integration_id == "google":
            params["access_type"] = "offline"
            params["prompt"] = "consent"

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{config['authorize_url']}?{query}"

    async def handle_oauth_callback(self, integration_id: str, code: str, state: str) -> OAuthConnection:
        import httpx

        stored = await redis_client.get(f"oauth_state:{state}")
        if not stored:
            raise ValueError("Invalid or expired OAuth state")

        user_id, expected_integration = stored.split(":", 1)
        if expected_integration != integration_id:
            raise ValueError("Integration mismatch")
        await redis_client.delete(f"oauth_state:{state}")

        config = OAUTH_CONFIGS[integration_id]
        client_id = getattr(settings, config["client_id_key"])
        client_secret = getattr(settings, config["client_secret_key"])
        callback_url = f"{settings.FRONTEND_URL}/api/v1/integrations/{integration_id}/oauth/callback"

        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": callback_url,
            }
            if integration_id == "github":
                token_data["grant_type"] = "authorization_code"
                headers = {"Accept": "application/json"}
            else:
                token_data["grant_type"] = "authorization_code"
                headers = {"Content-Type": "application/x-www-form-urlencoded"}

            resp = await client.post(config["token_url"], data=token_data, headers=headers)
            resp.raise_for_status()
            tokens = resp.json()

        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in")

        import uuid
        connection = OAuthConnection(
            user_id=uuid.UUID(user_id),
            integration_id=integration_id,
            access_token_encrypted=encrypt_token(access_token),
            refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
            token_expires_at=datetime.now(timezone.utc).replace(second=0) if not expires_in else None,
            scopes=config["scopes"],
        )
        self.db.add(connection)
        await self.db.flush()
        logger.info("oauth_connected", user_id=user_id, integration=integration_id)
        return connection

    async def get_access_token(self, user_id, integration_id: str) -> str:
        result = await self.db.execute(
            select(OAuthConnection).where(
                OAuthConnection.user_id == user_id,
                OAuthConnection.integration_id == integration_id,
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            raise ValueError(f"No connection found for {integration_id}")
        return decrypt_token(connection.access_token_encrypted)

    async def disconnect(self, user_id, integration_id: str):
        result = await self.db.execute(
            select(OAuthConnection).where(
                OAuthConnection.user_id == user_id,
                OAuthConnection.integration_id == integration_id,
            )
        )
        connection = result.scalar_one_or_none()
        if connection:
            await self.db.delete(connection)
            logger.info("oauth_disconnected", user_id=str(user_id), integration=integration_id)
