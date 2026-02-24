from pydantic import BaseModel


class IntegrationResponse(BaseModel):
    id: str
    name: str
    provider: str
    category: str | None
    is_active: bool
    is_connected: bool = False

    model_config = {"from_attributes": True}


class OAuthAuthorizeResponse(BaseModel):
    authorization_url: str


class ConnectedIntegrationResponse(BaseModel):
    id: str
    integration_id: str
    integration_name: str
    scopes: list[str]
    connected_at: str


class ToolResponse(BaseModel):
    name: str
    description: str
    input_schema: dict
