"""发布调度器：基于 Redis zset 的定时/即时任务派发

流程：任务入队(zadd) → 轮询 loop 取到期任务 → 逐账号调用平台适配器 → 回写 item/task 状态
分布式部署时通过 Redis 锁保证同一任务只被一个实例执行。
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db.redis import KEY_PUBLISH_LOCK, KEY_PUBLISH_QUEUE, get_redis
from app.db.session import async_session_factory
from app.models.content import PublishItem, PublishTask
from app.models.enums import PublishItemStatus, PublishTaskStatus
from app.services.platforms import get_adapter

logger = logging.getLogger("publish.scheduler")

POLL_INTERVAL = 3  # 秒
LOCK_TTL = 600
RPA_ITEM_TTL = 1800  # RPA 条目 dispatched 超过该秒数无人回报则回收为 pending


def aggregate_task_status(task: PublishTask) -> None:
    """按 item 状态汇总 task 状态；仍有未完成 item 时保持 publishing"""
    statuses = [i.status for i in task.items]
    if any(
        s in (PublishItemStatus.pending.value, PublishItemStatus.publishing.value, PublishItemStatus.dispatched.value)
        for s in statuses
    ):
        task.status = PublishTaskStatus.publishing.value
        return
    success = statuses.count(PublishItemStatus.success.value)
    failed = len(statuses) - success
    task.status = (
        PublishTaskStatus.published.value if failed == 0
        else PublishTaskStatus.failed.value if success == 0
        else PublishTaskStatus.partial.value
    )


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def enqueue_task(task_id: int, score: datetime) -> None:
    """任务入队，score 为应执行时间"""
    redis = get_redis()
    ts = score.timestamp() if score.tzinfo else score.replace(tzinfo=timezone.utc).timestamp()
    await redis.zadd(KEY_PUBLISH_QUEUE, {str(task_id): ts})


async def dequeue_task(task_id: int) -> None:
    redis = get_redis()
    await redis.zrem(KEY_PUBLISH_QUEUE, str(task_id))


async def run_task(task_id: int) -> None:
    """执行一个发布任务：逐账号发布并回写状态"""
    async with async_session_factory() as session:
        task = await session.get(PublishTask, task_id)
        if task is None or task.status not in (PublishTaskStatus.scheduled.value, PublishTaskStatus.queued.value):
            return
        task.status = PublishTaskStatus.publishing.value
        await session.commit()

        from app.models.account import SocialAccount
        from app.models.content import Content

        content = await session.get(Content, task.content_id)
        items = (await session.execute(select(PublishItem).where(PublishItem.task_id == task_id))).scalars().all()
        account_ids = [i.account_id for i in items]
        accounts = {
            a.id: a
            for a in (
                await session.execute(select(SocialAccount).where(SocialAccount.id.in_(account_ids)))
            ).scalars()
        }

        for item in items:
            account = accounts.get(item.account_id)
            if account is None or account.auth_status != "valid":
                item.status = PublishItemStatus.failed.value
                item.fail_reason = "账号不存在或授权失效" if account is None else "账号授权已失效"
                continue
            # RPA 通道按账号 opt-in：server 不执行，条目保持 pending 等桌面端认领（与 mock 开关无关）
            if account.channel == "rpa":
                continue
            item.status = PublishItemStatus.publishing.value
            await session.commit()
            try:
                adapter = get_adapter(account)
                result = await adapter.publish(account, content, task.extras)
                item.status = PublishItemStatus.success.value
                item.platform_publish_id = result["platform_publish_id"]
                item.publish_url = result["publish_url"]
                item.published_at = _now()
            except Exception as e:  # noqa: BLE001 单账号失败不影响其他账号
                item.status = PublishItemStatus.failed.value
                item.fail_reason = str(e)[:255]
        # 汇总任务状态（RPA 任务此时可能仍含 dispatched，保持 publishing）
        aggregate_task_status(task)
        await session.commit()
        success = sum(1 for i in items if i.status == PublishItemStatus.success.value)
        failed = sum(1 for i in items if i.status == PublishItemStatus.failed.value)
        logger.info("发布任务 %s 派发完成：成功 %s / 失败 %s / 待客户端 %s", task_id, success, failed, len(items) - success - failed)


async def dispatch_due_tasks() -> int:
    """取出到期任务并派发，返回派发数量"""
    redis = get_redis()
    now_ts = datetime.now(timezone.utc).timestamp()
    due_ids = await redis.zrangebyscore(KEY_PUBLISH_QUEUE, "-inf", now_ts)
    count = 0
    for task_id in due_ids:
        # 抢锁：抢到才执行，防多实例重复发布
        lock_key = KEY_PUBLISH_LOCK.format(task_id=task_id)
        got = await redis.set(lock_key, "1", nx=True, ex=LOCK_TTL)
        if not got:
            await redis.zrem(KEY_PUBLISH_QUEUE, task_id)
            continue
        await redis.zrem(KEY_PUBLISH_QUEUE, task_id)
        asyncio.create_task(_run_locked(task_id, lock_key))
        count += 1
    return count


async def _run_locked(task_id: int, lock_key: str) -> None:
    try:
        await run_task(task_id)
    except Exception:
        logger.exception("发布任务 %s 执行异常", task_id)
        async with async_session_factory() as session:
            await session.execute(
                update(PublishTask)
                .where(PublishTask.id == task_id)
                .values(status=PublishTaskStatus.failed.value)
            )
            await session.commit()
    finally:
        await get_redis().delete(lock_key)


async def recover_stale_tasks() -> None:
    """服务重启后，把仍在 scheduled/publishing 的任务重新入队（崩溃恢复）"""
    async with async_session_factory() as session:
        tasks = (
            await session.execute(
                select(PublishTask).where(
                    PublishTask.status.in_([PublishTaskStatus.scheduled.value, PublishTaskStatus.publishing.value])
                )
            )
        ).scalars().all()
        for t in tasks:
            score = t.scheduled_at or (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=5))
            await enqueue_task(t.id, score)
        if tasks:
            logger.info("崩溃恢复：重新入队 %s 个任务", len(tasks))


async def recover_stale_rpa_items() -> int:
    """回收超时未回报的 RPA 条目（客户端崩溃/离线），置回 pending 等待重新认领"""
    cutoff = _now() - timedelta(seconds=RPA_ITEM_TTL)
    async with async_session_factory() as session:
        res = await session.execute(
            update(PublishItem)
            .where(PublishItem.status == PublishItemStatus.dispatched.value, PublishItem.updated_at < cutoff)
            .values(status=PublishItemStatus.pending.value, fail_reason=None)
        )
        await session.commit()
        if res.rowcount:
            logger.warning("RPA 回收：%s 个超时条目置回 pending", res.rowcount)
        return res.rowcount or 0


async def scheduler_loop() -> None:
    logger.info("发布调度器已启动，轮询间隔 %ss", POLL_INTERVAL)
    while True:
        try:
            await dispatch_due_tasks()
            await recover_stale_rpa_items()
        except Exception:
            logger.exception("调度轮询异常")
        await asyncio.sleep(POLL_INTERVAL)


def start_scheduler() -> asyncio.Task:
    return asyncio.create_task(scheduler_loop())
