from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.auth import UserOut


class TeamUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    audit_enabled: bool | None = None
    webhook_url: str | None = Field(default=None, max_length=512)


class InviteOut(BaseModel):
    invite_code: str
    expire_seconds: int


class JoinIn(BaseModel):
    invite_code: str


class MemberRoleIn(BaseModel):
    role: str = Field(pattern=r"^(admin|operator|auditor)$")


class AuditLogOut(BaseModel):
    id: int
    user_id: int
    action: str
    detail: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateIn(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    avatar: str | None = Field(default=None, max_length=512)
    password: str | None = Field(default=None, min_length=8, max_length=72)
