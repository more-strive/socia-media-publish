"""RPA 客户端协作：桌面端认领待执行条目并回报结果（抖音等无开放 API 平台）

流程：调度器跳过 rpa 通道账号（条目保持 pending、任务保持 publishing）→ 桌面端轮询
POST /claim 原子认领（pending→dispatched）→ 本地浏览器自动化执行 → POST /report 回写终态。
超时无人回报的条目由调度器回收为 pending（见 scheduler.recover_stale_rpa_items）。
"""
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.api.deps import CurrentUser, DbDep, require_roles
from app.core.exceptions import BizError, NotFoundError
from app.models.account import SocialAccount
from app.models.content import Content, PublishItem, PublishTask
from app.models.enums import PublishItemStatus, PublishTaskStatus, UserRole
from app.schemas.common import ok
from app.services.scheduler import aggregate_task_status

router = APIRouter(
    prefix="/publish/rpa",
    tags=["RPA 分发"],
    dependencies=[require_roles(UserRole.owner, UserRole.admin, UserRole.operator)],
)


class ClaimIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=64, description="客户端设备标识")
    capacity: int = Field(default=1, ge=1, le=10, description="本次最多认领条数")


class ReportIn(BaseModel):
    item_id: int
    success: bool
    platform_publish_id: str | None = Field(default=None, max_length=128)
    publish_url: str | None = Field(default=None, max_length=512)
    fail_reason: str | None = Field(default=None, max_length=255)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/claim", summary="认领待执行条目（桌面客户端轮询）")
async def claim(payload: ClaimIn, user: CurrentUser, db: DbDep):
    rows = (
        await db.execute(
            select(PublishItem, SocialAccount, PublishTask, Content)
            .join(SocialAccount, PublishItem.account_id == SocialAccount.id)
            .join(PublishTask, PublishItem.task_id == PublishTask.id)
            .join(Content, PublishTask.content_id == Content.id)
            .where(
                PublishItem.status == PublishItemStatus.pending.value,
                PublishTask.status == PublishTaskStatus.publishing.value,
                PublishTask.team_id == user.team_id,
                SocialAccount.channel == "rpa",
                SocialAccount.auth_status == "valid",
            )
            .order_by(PublishTask.scheduled_at.is_(None), PublishTask.scheduled_at, PublishItem.id)
            .limit(payload.capacity * 3)
        )
    ).all()

    claimed: list[dict] = []
    for item, account, task, content in rows:
        # 原子认领：条件更新防止多客户端抢单
        res = await db.execute(
            update(PublishItem)
            .where(PublishItem.id == item.id, PublishItem.status == PublishItemStatus.pending.value)
            .values(status=PublishItemStatus.dispatched.value)
        )
        if res.rowcount:
            claimed.append(
                {
                    "item_id": item.id,
                    "task_id": task.id,
                    "account": {
                        "id": account.id,
                        "platform": account.platform,
                        "nickname": account.nickname,
                        "note": account.note,
                    },
                    "content": {
                        "id": content.id,
                        "type": content.type,
                        "title": content.title,
                        "summary": content.summary,
                        "media": content.media,
                        "tags": content.tags,
                    },
                    "extras": task.extras,
                }
            )
        if len(claimed) >= payload.capacity:
            break
    await db.commit()
    return ok(claimed)


@router.post("/report", summary="回报执行结果")
async def report(payload: ReportIn, user: CurrentUser, db: DbDep):
    row = (
        await db.execute(
            select(PublishItem, PublishTask)
            .join(PublishTask, PublishItem.task_id == PublishTask.id)
            .where(PublishItem.id == payload.item_id, PublishTask.team_id == user.team_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("发布条目不存在")
    item, task = row

    if item.status == PublishItemStatus.success.value:
        return ok({"item_status": item.status, "task_status": task.status})  # 幂等
    if item.status != PublishItemStatus.dispatched.value:
        raise BizError(400, f"条目状态为 {item.status}，不能回报")

    if payload.success:
        item.status = PublishItemStatus.success.value
        item.platform_publish_id = payload.platform_publish_id
        item.publish_url = payload.publish_url
        item.published_at = _now()
    else:
        item.status = PublishItemStatus.failed.value
        item.fail_reason = (payload.fail_reason or "RPA 执行失败")[:255]
    await db.flush()
    await db.refresh(task, attribute_names=["items"])
    aggregate_task_status(task)
    await db.commit()
    return ok({"item_status": item.status, "task_status": task.status})


@router.get("/queue", summary="查看派发中的条目（观测用）")
async def queue(user: CurrentUser, db: DbDep):
    rows = (
        await db.execute(
            select(PublishItem, SocialAccount)
            .join(SocialAccount, PublishItem.account_id == SocialAccount.id)
            .join(PublishTask, PublishItem.task_id == PublishTask.id)
            .where(
                PublishItem.status == PublishItemStatus.dispatched.value,
                PublishTask.team_id == user.team_id,
            )
            .order_by(PublishItem.updated_at.desc())
        )
    ).all()
    return ok(
        [
            {
                "item_id": item.id,
                "task_id": item.task_id,
                "platform": account.platform,
                "account_nickname": account.nickname,
                "dispatched_at": item.updated_at,
            }
            for item, account in rows
        ]
    )
