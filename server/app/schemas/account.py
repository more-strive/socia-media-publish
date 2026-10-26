from datetime import datetime

from pydantic import BaseModel, Field


class AccountGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    sort: int = 0


class AccountGroupOut(BaseModel):
    id: int
    name: str
    sort: int

    model_config = {"from_attributes": True}


class AccountIn(BaseModel):
    """新增托管账号（mock 授权：真实场景应跳转平台授权页/扫码）"""

    platform: str
    nickname: str = Field(min_length=1, max_length=128)
    platform_account_id: str | None = None
    group_id: int | None = None
    operator_id: int | None = None
    proxy_id: int | None = None
    channel: str = Field(default="open_api", pattern=r"^(open_api|rpa|cloud_app)$")
    region: str | None = None
    fans_count: int = 0
    note: str | None = None


class AccountUpdateIn(BaseModel):
    auth_status: str | None = Field(default=None, pattern=r"^(valid|expired|invalid)$")
    group_id: int | None = None
    operator_id: int | None = None
    proxy_id: int | None = None
    region: str | None = None
    note: str | None = None
    nickname: str | None = Field(default=None, min_length=1, max_length=128)
    last_probe_screenshot: str | None = Field(default=None, max_length=512)


class AccountOut(BaseModel):
    id: int
    platform: str
    platform_account_id: str | None = None
    nickname: str
    avatar: str | None = None
    fans_count: int
    auth_status: str
    group_id: int | None = None
    group_name: str | None = None
    operator_id: int | None = None
    proxy_id: int | None = None
    channel: str
    region: str | None = None
    last_active_at: datetime | None = None
    last_probe_screenshot: str | None = None
    note: str | None = None

    model_config = {"from_attributes": True}


class BatchCheckOut(BaseModel):
    total: int
    expired: int


class ProxyIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scheme: str = Field(default="http", pattern=r"^(http|https|socks5)$")
    host: str
    port: int = Field(ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    region: str | None = None


class ProxyOut(BaseModel):
    id: int
    name: str
    scheme: str
    host: str
    port: int
    # 认证代理凭据需下发到桌面端应答 407 挑战（仅团队角色可见，HTTPS 传输）
    username: str | None = None
    password: str | None = None
    region: str | None = None
    status: str
    last_check_at: datetime | None = None

    model_config = {"from_attributes": True}
