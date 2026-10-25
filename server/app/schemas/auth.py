from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class RegisterIn(BaseModel):
    phone: str | None = Field(default=None, pattern=r"^1\d{10}$")
    email: str | None = None
    password: str = Field(min_length=8, max_length=72)
    nickname: str = Field(min_length=1, max_length=64)
    team_name: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def check_contact(self):
        if not self.phone and not self.email:
            raise ValueError("手机号与邮箱至少填一项")
        return self


class PasswordLoginIn(BaseModel):
    account: str = Field(description="手机号或邮箱")
    password: str


class SmsSendIn(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")


class SmsLoginIn(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    code: str = Field(min_length=4, max_length=8)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: int
    team_id: int
    nickname: str
    avatar: str | None = None
    phone: str | None = None
    email: str | None = None
    role: str
    status: str
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class TeamBrief(BaseModel):
    id: int
    name: str
    plan_id: int | None = None
    plan_expire_at: datetime | None = None
    seats_total: int
    credits: int
    audit_enabled: bool
    webhook_url: str | None = None

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    user: UserOut
    team: TeamBrief
