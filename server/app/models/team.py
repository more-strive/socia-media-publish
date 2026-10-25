"""团队与成员（席位制）"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), comment="团队名称")
    plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("plans.id", use_alter=True), comment="当前套餐", default=None
    )
    plan_expire_at: Mapped[datetime | None] = mapped_column(DateTime, comment="套餐到期时间")
    seats_total: Mapped[int] = mapped_column(default=3, comment="席位数")
    credits: Mapped[int] = mapped_column(default=1000, comment="AI 积分余额")
    audit_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="发布前审核流开关")
    webhook_url: Mapped[str | None] = mapped_column(String(512), comment="汇总数据推送 webhook（飞书/钉钉）")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True, comment="所属团队")
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, comment="手机号")
    email: Mapped[str | None] = mapped_column(String(128), unique=True, comment="邮箱")
    password_hash: Mapped[str | None] = mapped_column(String(128), comment="密码哈希（验证码登录用户可为空）")
    nickname: Mapped[str] = mapped_column(String(64), comment="昵称")
    avatar: Mapped[str | None] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(16), default="operator", comment="角色 owner/admin/operator/auditor")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="状态")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    team: Mapped[Team] = relationship(lazy="joined")
