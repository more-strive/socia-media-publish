"""AI 创作：文案/视频/数字人任务（积分计费）"""
import asyncio

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, PageDep
from app.core.exceptions import BizError, NotFoundError
from app.core.config import settings
from app.models.ai import AITask
from app.models.enums import AITaskStatus, AITaskType
from app.models.team import Team
from app.schemas.ai import CREDITS_TABLE, AITaskIn, AITaskOut, CreditsOut
from app.schemas.common import ok
from app.services import ai_service
from app.db.session import async_session_factory

router = APIRouter(prefix="/ai", tags=["AI创作"])


@router.get("/credits", summary="积分余额")
async def credits(user: CurrentUser, db: DbDep):
    team = await db.get(Team, user.team_id)
    return ok(CreditsOut(credits=team.credits).model_dump())


@router.post("/tasks", summary="创建 AI 任务（copy 同步返回，video 等异步轮询）")
async def create_task(payload: AITaskIn, user: CurrentUser, db: DbDep):
    cost = CREDITS_TABLE[payload.task_type]
    team = await db.get(Team, user.team_id)
    if team.credits < cost:
        raise BizError(402, f"积分不足：需 {cost}，当前 {team.credits}")

    task = AITask(
        team_id=user.team_id,
        creator_id=user.id,
        task_type=payload.task_type,
        provider="ark" if payload.task_type == AITaskType.copy.value and settings.ark_api_key
        else "seedance" if payload.task_type == AITaskType.video.value and settings.seedance_api_key
        else "mock",
        prompt=payload.prompt,
        params=payload.params,
        status=AITaskStatus.pending.value,
        credits_cost=cost,
    )
    db.add(task)
    team.credits -= cost
    await db.commit()

    if payload.task_type == AITaskType.copy.value:
        # 文案：同步生成
        try:
            text = await ai_service.generate_copy(
                payload.prompt,
                payload.params.get("platform", "xhs") if payload.params else "xhs",
            )
            task.result = {"text": text}
            task.status = AITaskStatus.succeeded.value
            await db.commit()
        except Exception as e:  # noqa: BLE001
            task.status = AITaskStatus.failed.value
            task.error = str(e)[:255]
            team.credits += cost  # 失败退还积分
            await db.commit()
            raise BizError(500, f"生成失败：{task.error}")
    else:
        # 视频/数字人/声音克隆：后台异步执行
        task.status = AITaskStatus.running.value
        await db.commit()
        asyncio.create_task(_run_async_task(task.id, payload))
    return ok(AITaskOut.model_validate(task).model_dump(mode="json"))


async def _run_async_task(task_id: int, payload: AITaskIn) -> None:
    """异步执行长任务，失败退还积分"""
    async with async_session_factory() as session:
        task = await session.get(AITask, task_id)
        team = await session.get(Team, task.team_id)
        try:
            if payload.task_type == AITaskType.video.value:
                result = await ai_service.generate_video(payload.prompt, payload.params)
            else:
                # 数字人 / 声音克隆：当前为 mock
                await ai_service.mock_run_with_delay()
                result = {"demo": True, "type": payload.task_type}
            task.result = result
            task.status = AITaskStatus.succeeded.value
        except Exception as e:  # noqa: BLE001
            task.status = AITaskStatus.failed.value
            task.error = str(e)[:255]
            if team:
                team.credits += task.credits_cost
        await session.commit()


@router.get("/tasks", summary="任务列表")
async def list_tasks(user: CurrentUser, db: DbDep, page: PageDep, status: str | None = None):
    conds = [AITask.team_id == user.team_id]
    if status:
        conds.append(AITask.status == status)
    total = await db.scalar(select(func.count()).select_from(AITask).where(*conds))
    rows = (
        await db.execute(
            select(AITask).where(*conds).order_by(AITask.id.desc()).offset(page.offset).limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [AITaskOut.model_validate(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.get("/tasks/{task_id}", summary="任务详情（轮询获取结果）")
async def get_task(task_id: int, user: CurrentUser, db: DbDep):
    task = await db.scalar(select(AITask).where(AITask.id == task_id, AITask.team_id == user.team_id))
    if task is None:
        raise NotFoundError("任务不存在")
    return ok(AITaskOut.model_validate(task).model_dump(mode="json"))
