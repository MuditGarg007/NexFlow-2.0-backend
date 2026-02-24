"""
Seed script — populates the integrations table with supported services.
Run once after initial migration: python scripts/seed.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import get_settings
from app.models.integration import Integration
from app.database import Base

settings = get_settings()

INTEGRATIONS = [
    {
        "id": "github",
        "name": "GitHub",
        "provider": "github",
        "category": "Development",
        "oauth_config": {
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scopes": ["repo", "user"],
        },
        "available_tools": ["list_repos", "create_issue", "list_pull_requests", "search_repos"],
    },
    {
        "id": "google",
        "name": "Google Workspace",
        "provider": "google",
        "category": "Productivity",
        "oauth_config": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/photoslibrary.readonly",
            ],
        },
        "available_tools": [
            "list_emails", "send_email", "read_email",
            "list_events", "create_event",
            "list_files", "search_files",
            "list_albums", "search_photos",
        ],
    },
    {
        "id": "linkedin",
        "name": "LinkedIn",
        "provider": "linkedin",
        "category": "Social",
        "oauth_config": {
            "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
            "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
            "scopes": ["openid", "profile", "email", "w_member_social"],
        },
        "available_tools": ["get_profile", "create_post"],
    },
]


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession)

    async with async_session() as session:
        for data in INTEGRATIONS:
            integration = Integration(**data)
            await session.merge(integration)
        await session.commit()
        print(f"Seeded {len(INTEGRATIONS)} integrations.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
