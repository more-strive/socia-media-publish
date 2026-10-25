"""私信评论管理与话术库"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin
from app.models.enums import MessageDirection, ReplyRuleType


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("social_accounts.id"), index=True)
    msg_type: Mapped[str] = mapped_column(String(16), comment="comment/dm")
    direction: Mapped[str] = mapped_column(String(16), comment="inbound/outbound")
    platform_msg_id: Mapped[str | None] = mapped_column(String(128), comment="平台侧消息 ID")
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("messages.id"), comment="上级评论（多级嵌套）")
    reply_to_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("messages.id"), comment="回复的目标消息")
    content: Mapped[str] = mapped_column(Text)
    from_name: Mapped[str | None] = mapped_column(String(128), comment="发送者昵称")
    from_avatar: Mapped[str | None] = mapped_column(String(512))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    auto_reply: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否命中自动回复")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class ReplyRule(TimestampMixin, Base):
    __tablename__ = "reply_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    rule_type: Mapped[str] = mapped_column(String(16), default=ReplyRuleType.keyword.value)
    keywords: Mapped[list | None] = mapped_column(JSON, comment="触发关键词列表")
    content: Mapped[str] = mapped_column(Text, comment="回复内容")
    status: Mapped[bool] = mapped_column(Boolean, default=True, comment="启用状态")


class Script(TimestampMixin, Base):
    """个人话术 / 话术库（分组管理）"""

    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), comment="个人话术归属，空为团队公共")
    group_name: Mapped[str] = mapped_column(String(64), default="默认分组")
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
