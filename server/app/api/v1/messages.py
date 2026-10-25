"""私信评论管理：统一收件、回复、已读、自动回复规则、话术库、模拟入站"""
import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, PageDep
from app.core.exceptions import BizError, NotFoundError
from app.models.account import SocialAccount
from app.models.interaction import Message, ReplyRule, Script
from app.models.enums import MessageDirection, MessageType
from app.schemas.common import ok
from app.schemas.interaction import (
    MessageOut,
    MessageReplyIn,
    MockInboundIn,
    ReadIn,
    ReplyRuleIn,
    ReplyRuleOut,
    ScriptIn,
    ScriptOut,
    UnreadCountOut,
)
from app.services import message_service

router = APIRouter(prefix="/messages", tags=["私信评论"])


async def _get_account(db, team_id: int, account_id: int) -> SocialAccount:
    account = await db.scalar(
        select(SocialAccount).where(SocialAccount.id == account_id, SocialAccount.team_id == team_id)
    )
    if account is None:
        raise NotFoundError("账号不存在")
    return account


@router.get("", summary="统一收件箱（评论/私信）")
async def list_messages(
    user: CurrentUser,
    db: DbDep,
    page: PageDep,
    msg_type: str | None = None,
    account_id: int | None = None,
    is_read: bool | None = None,
    direction: str | None = None,
):
    conds = [Message.team_id == user.team_id, Message.direction == MessageDirection.inbound.value]
    if msg_type:
        conds.append(Message.msg_type == msg_type)
    if account_id:
        conds.append(Message.account_id == account_id)
    if is_read is not None:
        conds.append(Message.is_read.is_(is_read))
    if direction:
        conds.append(Message.direction == direction)

    total = await db.scalar(select(func.count()).select_from(Message).where(*conds))
    rows = (
        await db.execute(
            select(Message).where(*conds).order_by(Message.id.desc()).offset(page.offset).limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [MessageOut.model_validate(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.get("/unread-count", summary="未读数（评论/私信分计）")
async def unread_count(user: CurrentUser, db: DbDep):
    base = [Message.team_id == user.team_id, Message.direction == MessageDirection.inbound.value, Message.is_read.is_(False)]
    comment = await db.scalar(
        select(func.count()).select_from(Message).where(*base, Message.msg_type == MessageType.comment.value)
    )
    dm = await db.scalar(
        select(func.count()).select_from(Message).where(*base, Message.msg_type == MessageType.dm.value)
    )
    return ok(UnreadCountOut(comment=comment, dm=dm).model_dump())


@router.post("/{message_id}/reply", summary="回复评论/私信")
async def reply(message_id: int, payload: MessageReplyIn, user: CurrentUser, db: DbDep):
    inbound = await db.scalar(
        select(Message).where(Message.id == message_id, Message.team_id == user.team_id)
    )
    if inbound is None:
        raise NotFoundError("消息不存在")
    reply = await message_service.create_reply(db, inbound, payload.content)
    inbound.is_read = True
    await db.commit()
    return ok(MessageOut.model_validate(reply).model_dump(mode="json"))


@router.post("/read", summary="批量标记已读")
async def mark_read(payload: ReadIn, user: CurrentUser, db: DbDep):
    rows = (
        await db.execute(
            select(Message).where(Message.id.in_(payload.ids), Message.team_id == user.team_id)
        )
    ).scalars().all()
    for r in rows:
        r.is_read = True
    await db.commit()
    return ok(message=f"已标记 {len(rows)} 条")


@router.post("/mock/inbound", summary="模拟平台消息推送（开发联调用）")
async def mock_inbound(payload: MockInboundIn, user: CurrentUser, db: DbDep):
    await _get_account(db, user.team_id, payload.account_id)
    inbound = Message(
        team_id=user.team_id,
        account_id=payload.account_id,
        msg_type=payload.msg_type,
        direction=MessageDirection.inbound.value,
        parent_id=payload.parent_id,
        content=payload.content,
        from_name=payload.from_name,
        platform_msg_id=f"mock_{uuid.uuid4().hex[:12]}",
    )
    db.add(inbound)
    await db.flush()
    # 命中自动回复规则则直接回一条
    auto_content = await message_service.match_auto_reply(db, user.team_id, inbound)
    if auto_content:
        await message_service.create_reply(db, inbound, auto_content, auto=True)
    await db.commit()
    return ok(MessageOut.model_validate(inbound).model_dump(mode="json"))


# ---------- 自动回复规则 ----------


@router.get("/reply-rules", summary="自动回复规则列表")
async def list_rules(user: CurrentUser, db: DbDep):
    rows = (
        await db.execute(select(ReplyRule).where(ReplyRule.team_id == user.team_id).order_by(ReplyRule.id.desc()))
    ).scalars().all()
    return ok([ReplyRuleOut.model_validate(r).model_dump() for r in rows])


@router.post("/reply-rules", summary="新建规则（关键词/欢迎语）")
async def create_rule(payload: ReplyRuleIn, user: CurrentUser, db: DbDep):
    if payload.rule_type == "keyword" and not payload.keywords:
        raise BizError(400, "关键词规则必须提供 keywords")
    rule = ReplyRule(team_id=user.team_id, **payload.model_dump())
    db.add(rule)
    await db.commit()
    return ok(ReplyRuleOut.model_validate(rule).model_dump())


@router.put("/reply-rules/{rule_id}", summary="修改规则")
async def update_rule(rule_id: int, payload: ReplyRuleIn, user: CurrentUser, db: DbDep):
    rule = await db.scalar(select(ReplyRule).where(ReplyRule.id == rule_id, ReplyRule.team_id == user.team_id))
    if rule is None:
        raise NotFoundError("规则不存在")
    for k, v in payload.model_dump().items():
        setattr(rule, k, v)
    await db.commit()
    return ok(ReplyRuleOut.model_validate(rule).model_dump())


@router.delete("/reply-rules/{rule_id}", summary="删除规则")
async def delete_rule(rule_id: int, user: CurrentUser, db: DbDep):
    rule = await db.scalar(select(ReplyRule).where(ReplyRule.id == rule_id, ReplyRule.team_id == user.team_id))
    if rule is None:
        raise NotFoundError("规则不存在")
    await db.delete(rule)
    await db.commit()
    return ok(message="已删除")


# ---------- 话术库 ----------


@router.get("/scripts", summary="话术库列表（个人 + 团队公共）")
async def list_scripts(user: CurrentUser, db: DbDep, group_name: str | None = None):
    conds = [Script.team_id == user.team_id]
    rows = (
        await db.execute(select(Script).where(*conds).order_by(Script.id.desc()))
    ).scalars().all()
    # 个人话术只归本人可见
    visible = [r for r in rows if r.owner_id in (None, user.id)]
    if group_name:
        visible = [r for r in visible if r.group_name == group_name]
    return ok([ScriptOut.model_validate(r).model_dump() for r in visible])


@router.post("/scripts", summary="新建话术")
async def create_script(payload: ScriptIn, user: CurrentUser, db: DbDep):
    # 普通成员只能存个人话术或团队公共（owner/admin 可指定归属）
    owner_id = payload.owner_id
    if owner_id is not None and user.role not in ("owner", "admin"):
        owner_id = user.id
    script = Script(team_id=user.team_id, owner_id=owner_id, **payload.model_dump(exclude={"owner_id"}))
    db.add(script)
    await db.commit()
    return ok(ScriptOut.model_validate(script).model_dump())


@router.put("/scripts/{script_id}", summary="修改话术")
async def update_script(script_id: int, payload: ScriptIn, user: CurrentUser, db: DbDep):
    script = await db.scalar(select(Script).where(Script.id == script_id, Script.team_id == user.team_id))
    if script is None:
        raise NotFoundError("话术不存在")
    if script.owner_id not in (None, user.id) and user.role not in ("owner", "admin"):
        raise BizError(403, "不能修改他人个人话术")
    for k, v in payload.model_dump().items():
        setattr(script, k, v)
    await db.commit()
    return ok(ScriptOut.model_validate(script).model_dump())


@router.delete("/scripts/{script_id}", summary="删除话术")
async def delete_script(script_id: int, user: CurrentUser, db: DbDep):
    script = await db.scalar(select(Script).where(Script.id == script_id, Script.team_id == user.team_id))
    if script is None:
        raise NotFoundError("话术不存在")
    if script.owner_id not in (None, user.id) and user.role not in ("owner", "admin"):
        raise BizError(403, "不能删除他人个人话术")
    await db.delete(script)
    await db.commit()
    return ok(message="已删除")
