import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.models.user import User
from app.config import get_settings
from app.redis import redis_client
from app.dependencies import create_access_token, create_refresh_token
from app.utils.logger import get_logger

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, email: str, password: str, display_name: str | None = None) -> User:
        result = await self.db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")

        user = User(
            email=email,
            hashed_password=pwd_context.hash(password),
            display_name=display_name,
        )
        self.db.add(user)
        await self.db.flush()
        logger.info("user_registered", user_id=str(user.id), email=email)
        return user

    async def login(self, email: str, password: str) -> dict:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not pwd_context.verify(password, user.hashed_password):
            raise ValueError("Invalid credentials")

        user_id = str(user.id)
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        # store refresh token JTI in redis for revocation
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload["jti"]
        await redis_client.setex(f"refresh:{jti}", settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, user_id)

        logger.info("user_logged_in", user_id=user_id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def refresh_tokens(self, refresh_token: str) -> dict:
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            raise ValueError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        jti = payload.get("jti")
        user_id = payload.get("sub")

        stored = await redis_client.get(f"refresh:{jti}")
        if not stored:
            raise ValueError("Refresh token revoked or expired")

        # revoke old, issue new
        await redis_client.delete(f"refresh:{jti}")
        new_access = create_access_token(user_id)
        new_refresh = create_refresh_token(user_id)

        new_payload = jwt.decode(new_refresh, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        await redis_client.setex(f"refresh:{new_payload['jti']}", settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, user_id)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def logout(self, refresh_token: str):
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            jti = payload.get("jti")
            if jti:
                await redis_client.delete(f"refresh:{jti}")
        except JWTError:
            pass  # silently ignore invalid tokens on logout
