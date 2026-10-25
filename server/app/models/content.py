"""内容与发布任务（一键分发核心表）"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin
from app.models.enums import (
    ContentStatus,
    ContentType,
    PublishItemStatus,
    PublishMode,
    PublishTaskStatus,
)


class Content(TimestampMixin, Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(16), comment="内容类型 video/article/images")
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(String(512), comment="摘要（公众号/头条）")
    body: Mapped[str | None] = mapped_column(Text, comment="正文（长文 HTML/Markdown）")
    media: Mapped[list | None] = mapped_column(JSON, comment="素材 URL 列表")
    cover: Mapped[str | None] = mapped_column(String(512), comment="封面")
    tags: Mapped[list | None] = mapped_column(JSON, comment="标签")
    status: Mapped[str] = mapped_column(default=ContentStatus.draft.value, comment="draft/reviewing/approved/rejected")
    review_note: Mapped[str | None] = mapped_column(String(255))


class PublishTask(TimestampMixin, Base):
    __tablename__ = "publish_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    content_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contents.id"), index=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(16), default=PublishMode.immediate.value)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, comment="定时发布时间")
    status: Mapped[str] = mapped_column(default=PublishTaskStatus.scheduled.value, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), comment="审核人")
    review_note: Mapped[str | None] = mapped_column(String(255))
    extras: Mapped[dict | None] = mapped_column(JSON, comment="平台级设置：原创声明/合集/分类等")

    content: Mapped[Content] = relationship(lazy="joined")
    items: Mapped[list["PublishItem"]] = relationship(back_populates="task", lazy="selectin")


class PublishItem(TimestampMixin, Base):
    __tablename__ = "publish_items"
    __table_args__ = (Index("ix_publish_items_task_status", "task_id", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("publish_tasks.id"), index=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("social_accounts.id"), index=True)
    status: Mapped[str] = mapped_column(default=PublishItemStatus.pending.value)
    platform_publish_id: Mapped[str | None] = mapped_column(String(128), comment="平台侧作品 ID")
    publish_url: Mapped[str | None] = mapped_column(String(512))
    fail_reason: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    task: Mapped[PublishTask] = relationship(back_populates="items")
