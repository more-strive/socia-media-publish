"""私信/评论自动回复匹配"""
from sqlalchemy import select

from app.models.interaction import Message, ReplyRule
from app.models.enums import MessageDirection


async def match_auto_reply(session, team_id: int, inbound: Message) -> str | None:
    """按关键词规则匹配自动回复内容；无命中返回 None"""
    rules = (
        await session.execute(
            select(ReplyRule).where(ReplyRule.team_id == team_id, ReplyRule.status.is_(True))
        )
    ).scalars().all()
    text = (inbound.content or "").lower()
    for rule in rules:
        if rule.rule_type == "keyword":
            for kw in rule.keywords or []:
                if kw and kw.lower() in text:
                    return rule.content
    return None


async def create_reply(session, inbound: Message, reply_content: str, auto: bool = False) -> Message:
    """以托管账号身份回复一条消息/评论"""
    reply = Message(
        team_id=inbound.team_id,
        account_id=inbound.account_id,
        msg_type=inbound.msg_type,
        direction=MessageDirection.outbound.value,
        parent_id=inbound.parent_id,  # 保持同一评论楼层
        reply_to_id=inbound.id,
        content=reply_content,
        auto_reply=auto,
    )
    session.add(reply)
    return reply
