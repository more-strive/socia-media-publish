"""账号托管：多平台账号、分组、代理 IP"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin
from app.models.enums import AuthStatus, ProxyStatus


class AccountGroup(TimestampMixin, Base):
    __tablename__ = "account_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(64), comment="分组名")
    sort: Mapped[int] = mapped_column(default=0)


class SocialAccount(TimestampMixin, Base):
    __tablename__ = "social_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("account_groups.id"), index=True)
    platform: Mapped[str] = mapped_column(String(20), comment="平台")
    platform_account_id: Mapped[str | None] = mapped_column(String(128), comment="平台侧账号 ID")
    nickname: Mapped[str] = mapped_column(String(128), comment="账号昵称")
    avatar: Mapped[str | None] = mapped_column(String(512))
    fans_count: Mapped[int] = mapped_column(default=0, comment="粉丝数快照")
    auth_status: Mapped[str] = mapped_column(String(20), default=AuthStatus.valid.value, comment="授权状态")
    auth_payload: Mapped[str | None] = mapped_column(Text, comment="授权凭据（cookie/token，加密存储）")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), comment="运营人/负责人")
    proxy_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("proxy_ips.id"), comment="绑定代理")
    channel: Mapped[str] = mapped_column(String(20), default="open_api", comment="发布通道 open_api/rpa/cloud_app")
    region: Mapped[str | None] = mapped_column(String(64), comment="网络区域（IP 归属地）")
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最近检测时间")
    note: Mapped[str | None] = mapped_column(String(255))

    group: Mapped[AccountGroup | None] = relationship(lazy="joined")


class ProxyIP(TimestampMixin, Base):
    __tablename__ = "proxy_ips"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    scheme: Mapped[str] = mapped_column(String(10), default="http")
    host: Mapped[str] = mapped_column(String(128))
    port: Mapped[int] = mapped_column()
    username: Mapped[str | None] = mapped_column(String(64))
    password: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(64), comment="IP 归属地")
    status: Mapped[str] = mapped_column(String(20), default=ProxyStatus.unknown.value)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime)
