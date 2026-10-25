"""一键分发：发布任务（即时/定时）、审核流、发布日历"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, PageDep
from app.core.exceptions import BizError, NotFoundError
from app.models.account import SocialAccount
from app.models.content import Content, PublishItem, PublishTask
from app.models.enums import (
    ContentStatus,
    PublishMode,
    PublishTaskStatus,
    UserRole,
)
from app.models.team import Team
from app.schemas.common import ok
from app.schemas.content import CalendarDayOut, PublishTaskIn, PublishTaskOut, ReviewIn
from app.services.scheduler import dequeue_task, enqueue_task

router = APIRouter(prefix="/publish", tags=["一键分发"])

_UTC = timezone.utc


def _task_out(t: PublishTask) -> dict:
    data = PublishTaskOut.model_validate(t).model_dump(mode="json")
    data["content_title"] = t.content.title if t.content else None
    statuses = [i.status for i in t.items]
    data["item_count"] = len(statuses)
    data["success_count"] = statuses.count("success")
    data["failed_count"] = statuses.count("failed")
    return data


@router.post("/tasks", summary="创建发布任务：1 内容 → 多账号（支持定时）")
async def create_task(payload: PublishTaskIn, user: CurrentUser, db: DbDep):
    content = await db.scalar(
        select(Content).where(Content.id == payload.content_id, Content.team_id == user.team_id)
    )
    if content is None:
        raise NotFoundError("内容不存在")

    team = await db.get(Team, user.team_id)
    # 审核流：开启审核时，内容必须已通过；owner/admin 发可跳过任务审核
    if team.audit_enabled and content.status != ContentStatus.approved.value:
        raise BizError(400, "内容尚未通过审核，不能发布")

    accounts = (
        await db.execute(
            select(SocialAccount).where(
                SocialAccount.id.in_(payload.account_ids), SocialAccount.team_id == user.team_id
            )
        )
    ).scalars().all()
    if len(accounts) != len(set(payload.account_ids)):
        raise BizError(400, "存在无效账号")

    now = datetime.now(_UTC).replace(tzinfo=None)
    if payload.mode == PublishMode.scheduled.value:
        if payload.scheduled_at is None:
            raise BizError(400, "定时发布必须提供 scheduled_at")
        # 入库统一存 UTC
        scheduled = (
            payload.scheduled_at
            if payload.scheduled_at.tzinfo is None
            else payload.scheduled_at.astimezone(_UTC).replace(tzinfo=None)
        )
        if scheduled <= now:
            raise BizError(400, "定时时间必须晚于当前时间")

    # 是否需要任务级审核：开启审核流且创建者非 owner/admin
    need_review = team.audit_enabled and user.role not in (UserRole.owner.value, UserRole.admin.value)
    status = PublishTaskStatus.reviewing.value if need_review else PublishTaskStatus.scheduled.value

    task = PublishTask(
        team_id=user.team_id,
        content_id=content.id,
        creator_id=user.id,
        mode=payload.mode,
        scheduled_at=scheduled if payload.mode == PublishMode.scheduled.value else now,
        status=status,
        extras=payload.extras,
    )
    db.add(task)
    await db.flush()
    for account_id in set(payload.account_ids):
        db.add(PublishItem(task_id=task.id, account_id=account_id))
    await db.commit()
    await db.refresh(task, attribute_names=["items", "content"])  # 预加载关系，避免异步懒加载报错

    # 无需审核的任务直接入队（即时任务 score=now）
    if not need_review:
        score = task.scheduled_at or now
        await enqueue_task(task.id, score)
    return ok(_task_out(task))


@router.get("/tasks", summary="任务列表")
async def list_tasks(
    user: CurrentUser,
    db: DbDep,
    page: PageDep,
    status: str | None = None,
):
    conds = [PublishTask.team_id == user.team_id]
    if status:
        conds.append(PublishTask.status == status)
    total = await db.scalar(select(func.count()).select_from(PublishTask).where(*conds))
    rows = (
        await db.execute(
            select(PublishTask).where(*conds).order_by(PublishTask.id.desc()).offset(page.offset).limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [_task_out(t) for t in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.get("/tasks/{task_id}", summary="任务详情（含各账号子任务）")
async def get_task(task_id: int, user: CurrentUser, db: DbDep):
    task = await db.scalar(
        select(PublishTask).where(PublishTask.id == task_id, PublishTask.team_id == user.team_id)
    )
    if task is None:
        raise NotFoundError("任务不存在")
    return ok(_task_out(task))


@router.post("/tasks/{task_id}/cancel", summary="取消任务（仅未开始）")
async def cancel_task(task_id: int, user: CurrentUser, db: DbDep):
    task = await db.scalar(
        select(PublishTask).where(PublishTask.id == task_id, PublishTask.team_id == user.team_id)
    )
    if task is None:
        raise NotFoundError("任务不存在")
    if task.status not in (PublishTaskStatus.reviewing.value, PublishTaskStatus.scheduled.value):
        raise BizError(400, "任务已在执行或已结束，无法取消")
    task.status = PublishTaskStatus.canceled.value
    await db.commit()
    await dequeue_task(task.id)
    return ok(message="已取消")


@router.post("/tasks/{task_id}/review", summary="发布任务审核（审核员通过后入队）")
async def review_task(task_id: int, payload: ReviewIn, user: CurrentUser, db: DbDep):
    if user.role not in (UserRole.owner.value, UserRole.admin.value, UserRole.auditor.value):
        raise BizError(403, "仅审核员/管理员可审核")
    task = await db.scalar(
        select(PublishTask).where(PublishTask.id == task_id, PublishTask.team_id == user.team_id)
    )
    if task is None:
        raise NotFoundError("任务不存在")
    if task.status != PublishTaskStatus.reviewing.value:
        raise BizError(400, "任务不在待审核状态")
    task.reviewer_id = user.id
    task.review_note = payload.note
    if payload.approve:
        task.status = PublishTaskStatus.scheduled.value
        await db.commit()
        now = datetime.now(_UTC).replace(tzinfo=None)
        score = task.scheduled_at or now
        if score <= now:  # 原定时间已过，立即执行
            score = now
            task.scheduled_at = now
            await db.commit()
        await enqueue_task(task.id, score)
    else:
        task.status = PublishTaskStatus.canceled.value
        await db.commit()
    return ok(message="审核完成")


@router.get("/reviews", summary="待审核任务列表")
async def list_reviews(user: CurrentUser, db: DbDep, page: PageDep):
    conds = [PublishTask.team_id == user.team_id, PublishTask.status == PublishTaskStatus.reviewing.value]
    total = await db.scalar(select(func.count()).select_from(PublishTask).where(*conds))
    rows = (
        await db.execute(
            select(PublishTask).where(*conds).order_by(PublishTask.id.desc()).offset(page.offset).limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [_task_out(t) for t in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.get("/calendar", summary="发布日历（按日期聚合任务）")
async def calendar(
    user: CurrentUser,
    db: DbDep,
    start: date,
    end: date,
):
    if end < start:
        raise BizError(400, "end 必须不早于 start")
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())
    tasks = (
        await db.execute(
            select(PublishTask)
            .where(
                PublishTask.team_id == user.team_id,
                PublishTask.scheduled_at >= start_dt,
                PublishTask.scheduled_at < end_dt,
            )
            .order_by(PublishTask.scheduled_at)
        )
    ).scalars().all()
    by_day: dict[str, list] = {}
    for t in tasks:
        key = t.scheduled_at.strftime("%Y-%m-%d") if t.scheduled_at else "unscheduled"
        by_day.setdefault(key, []).append(_task_out(t))
    days = [
        CalendarDayOut(
            date=d,
            task_count=len(ts),
            account_count=sum(t["item_count"] for t in ts),
            tasks=ts,
        ).model_dump(mode="json")
        for d, ts in by_day.items()
    ]
    return ok(days)
