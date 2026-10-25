from datetime import datetime

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int
    account_id: int
    msg_type: str
    direction: str
    parent_id: int | None = None
    reply_to_id: int | None = None
    content: str
    from_name: str | None = None
    from_avatar: str | None = None
    is_read: bool
    auto_reply: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageReplyIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ReadIn(BaseModel):
    ids: list[int] = Field(min_length=1)


class MockInboundIn(BaseModel):
    """模拟平台消息推送（对接真实平台时由 webhook 回调替代）"""

    account_id: int
    msg_type: str = Field(pattern=r"^(comment|dm)$")
    content: str
    from_name: str = "测试用户"
    parent_id: int | None = None


class ReplyRuleIn(BaseModel):
    rule_type: str = Field(default="keyword", pattern=r"^(keyword|welcome|follow)$")
    keywords: list[str] | None = None
    content: str = Field(min_length=1, max_length=2000)
    status: bool = True


class ReplyRuleOut(BaseModel):
    id: int
    rule_type: str
    keywords: list[str] | None = None
    content: str
    status: bool

    model_config = {"from_attributes": True}


class ScriptIn(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=4000)
    group_name: str = Field(default="默认分组", max_length=64)
    owner_id: int | None = Field(default=None, description="指定成员则为个人话术，空为团队公共")


class ScriptOut(BaseModel):
    id: int
    group_name: str
    title: str
    content: str
    owner_id: int | None = None

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    comment: int
    dm: int
