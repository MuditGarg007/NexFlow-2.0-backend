from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.integration_service import IntegrationService
from app.mcp.registry import get_tools_for_integration
from app.schemas.integration import (
    IntegrationResponse, OAuthAuthorizeResponse, ConnectedIntegrationResponse, ToolResponse,
)
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


@router.get("/", response_model=list[IntegrationResponse])
async def list_integrations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = IntegrationService(db)
    all_integrations = await service.list_all()
    all_integrations = [i for i in all_integrations if i.provider != "linkedin"]  # TODO: remove when LinkedIn is ready
    connected_ids = await service.get_connected_integration_ids(user.id)
    return [
        IntegrationResponse(
            id=i.id, name=i.name, provider=i.provider,
            category=i.category, is_active=i.is_active,
            is_connected=i.id in connected_ids,
        )
        for i in all_integrations
    ]


@router.get("/connected", response_model=list[ConnectedIntegrationResponse])
async def list_connected(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = IntegrationService(db)
    connections = await service.list_connected(user.id)
    return [
        ConnectedIntegrationResponse(
            id=str(c.id),
            integration_id=c.integration_id,
            integration_name=c.integration_id,
            scopes=c.scopes,
            connected_at=c.connected_at.isoformat(),
        )
        for c in connections
    ]


@router.get("/{integration_id}/oauth/authorize", response_model=OAuthAuthorizeResponse)
async def authorize(integration_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = IntegrationService(db)
    try:
        url = service.build_authorize_url(integration_id, str(user.id))
        return OAuthAuthorizeResponse(authorization_url=url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{integration_id}/oauth/callback")
async def oauth_callback(integration_id: str, code: str, state: str, db: AsyncSession = Depends(get_db)):
    service = IntegrationService(db)
    try:
        await service.handle_oauth_callback(integration_id, code, state)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/integrations?connected={integration_id}")
    except ValueError as e:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/integrations?error={str(e)}")


@router.delete("/{integration_id}/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(integration_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = IntegrationService(db)
    await service.disconnect(user.id, integration_id)


@router.get("/{integration_id}/tools", response_model=list[ToolResponse])
async def list_tools(integration_id: str, user: User = Depends(get_current_user)):
    tools = get_tools_for_integration(integration_id)
    return [
        ToolResponse(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in tools
    ]
