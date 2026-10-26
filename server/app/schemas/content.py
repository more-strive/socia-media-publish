from datetime import datetime

from pydantic import BaseModel, Field


class ContentIn(BaseModel):
    type: str = Field(pattern=r"^(video|article|images)$")
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=512)
    body: str | None = None
    media: list[str] | None = None
    cover: str | None = None
    tags: list[str] | None = None


class ContentUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=512)
    body: str | None = None
    media: list[str] | None = None
    cover: str | None = None
    tags: list[str] | None = None
    type: str | None = Field(default=None, pattern=r"^(video|article|images)$")


class ContentOut(BaseModel):
    id: int
    type: str
    title: str
    summary: str | None = None
    body: str | None = None
    media: list[str] | None = None
    cover: str | None = None
    tags: list[str] | None = None
    status: str
    review_note: str | None = None
    creator_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AIGenerateIn(BaseModel):
    topic: str = Field(min_length=1, max_length=255, description="主题/关键词")
    platform: str = Field(default="xhs", description="目标平台风格：xhs/douyin/wechat_gzh")
    tone: str | None = Field(default=None, max_length=64, description="语气风格")


class ReviewIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=255)


class PublishTaskIn(BaseModel):
    content_id: int
    account_ids: list[int] = Field(min_length=1)
    mode: str = Field(default="immediate", pattern=r"^(immediate|scheduled)$")
    scheduled_at: datetime | None = None
    extras: dict | None = Field(default=None, description="平台级设置：原创/合集/分类/封面裁剪等")


class PublishItemOut(BaseModel):
    id: int
    account_id: int
    status: str
    platform_publish_id: str | None = None
    publish_url: str | None = None
    fail_reason: str | None = None
    published_at: datetime | None = None
    screenshots: list[str] | None = None

    model_config = {"from_attributes": True}


class PublishTaskOut(BaseModel):
    id: int
    content_id: int
    content_title: str | None = None
    mode: str
    scheduled_at: datetime | None = None
    status: str
    creator_id: int
    reviewer_id: int | None = None
    review_note: str | None = None
    item_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    created_at: datetime
    items: list[PublishItemOut] = []

    model_config = {"from_attributes": True}


class CalendarDayOut(BaseModel):
    date: str
    task_count: int
    account_count: int
    tasks: list[PublishTaskOut]
