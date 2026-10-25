"""数据统计：账号/作品/汇总、CSV 导出、飞书/钉钉推送"""
import csv
import io
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep
from app.core.exceptions import BizError
from app.models.account import SocialAccount
from app.models.content import PublishItem, PublishTask
from app.models.enums import PublishItemStatus
from app.models.stats import AccountDailyStat, ContentDailyStat
from app.models.team import Team
from app.schemas.common import ok
from app.schemas.stats import AccountStatOut, ContentStatRow, StatSeriesPoint, SummaryOut

router = APIRouter(prefix="/stats", tags=["数据统计"])


def _default_range(end: date | None, start: date | None) -> tuple[date, date]:
    end = end or date.today()
    start = start or end - timedelta(days=29)
    if start > end:
        raise BizError(400, "start 不能晚于 end")
    return start, end


@router.get("/accounts", summary="账号数据（时序 + 汇总）")
async def account_stats(
    user: CurrentUser,
    db: DbDep,
    start: date | None = None,
    end: date | None = None,
    account_ids: str | None = Query(default=None, description="逗号分隔的账号 ID，缺省为全部"),
):
    start, end = _default_range(end, start)
    acc_conds = [SocialAccount.team_id == user.team_id]
    if account_ids:
        ids = [int(x) for x in account_ids.split(",") if x.strip().isdigit()]
        acc_conds.append(SocialAccount.id.in_(ids))
    accounts = (await db.execute(select(SocialAccount).where(*acc_conds))).scalars().all()
    if not accounts:
        return ok([])
    acc_map = {a.id: a for a in accounts}
    rows = (
        await db.execute(
            select(AccountDailyStat).where(
                AccountDailyStat.team_id == user.team_id,
                AccountDailyStat.account_id.in_(acc_map.keys()),
                AccountDailyStat.date >= start,
                AccountDailyStat.date <= end,
            ).order_by(AccountDailyStat.date)
        )
    ).scalars().all()

    series_map: dict[int, list[StatSeriesPoint]] = {aid: [] for aid in acc_map}
    for r in rows:
        series_map[r.account_id].append(
            StatSeriesPoint(
                date=r.date, views=r.views, likes=r.likes, comments=r.comments,
                shares=r.shares, new_followers=r.new_followers,
            )
        )
    result = [
        AccountStatOut(
            account_id=aid,
            nickname=a.nickname,
            platform=a.platform,
            followers=a.fans_count,
            series=series_map[aid],
        ).model_dump(mode="json")
        for aid, a in acc_map.items()
    ]
    return ok(result)


@router.get("/contents", summary="作品数据排行")
async def content_stats(
    user: CurrentUser,
    db: DbDep,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    start, end = _default_range(end, start)
    rows = (
        await db.execute(
            select(
                ContentDailyStat.account_id,
                PublishItem.publish_url,
                PublishItem.published_at,
                PublishItem.task_id,
                func.sum(ContentDailyStat.views).label("views"),
                func.sum(ContentDailyStat.likes).label("likes"),
                func.sum(ContentDailyStat.comments).label("comments"),
                func.sum(ContentDailyStat.shares).label("shares"),
            )
            .join(PublishItem, PublishItem.id == ContentDailyStat.publish_item_id)
            .where(
                ContentDailyStat.team_id == user.team_id,
                ContentDailyStat.date >= start,
                ContentDailyStat.date <= end,
                PublishItem.status == PublishItemStatus.success.value,
            )
            .group_by(ContentDailyStat.publish_item_id)
            .order_by(func.sum(ContentDailyStat.views).desc())
            .limit(limit)
        )
    ).all()
    return ok(
        [
            ContentStatRow(
                content_id=r.task_id,
                title="",  # 标题由前端按 task_id 关联详情
                account_id=r.account_id,
                publish_url=r.publish_url,
                published_at=r.published_at,
                views=r.views or 0,
                likes=r.likes or 0,
                comments=r.comments or 0,
                shares=r.shares or 0,
            ).model_dump(mode="json")
            for r in rows
        ]
    )


@router.get("/summary", summary="团队单日汇总")
async def daily_summary(user: CurrentUser, db: DbDep, day: date | None = None):
    day = day or date.today()
    stat_result = await db.execute(
        select(
            func.coalesce(func.sum(AccountDailyStat.followers), 0),
            func.coalesce(func.sum(AccountDailyStat.new_followers), 0),
            func.coalesce(func.sum(AccountDailyStat.views), 0),
            func.coalesce(func.sum(AccountDailyStat.likes), 0),
            func.coalesce(func.sum(AccountDailyStat.comments), 0),
            func.coalesce(func.sum(AccountDailyStat.shares), 0),
        ).where(AccountDailyStat.team_id == user.team_id, AccountDailyStat.date == day)
    )
    stat = stat_result.one()
    account_count = await db.scalar(
        select(func.count()).select_from(SocialAccount).where(SocialAccount.team_id == user.team_id)
    )
    published = await db.scalar(
        select(func.count())
        .select_from(PublishItem)
        .join(PublishTask, PublishTask.id == PublishItem.task_id)
        .where(
            PublishTask.team_id == user.team_id,
            PublishItem.status == PublishItemStatus.success.value,
            func.date(PublishItem.published_at) == day,
        )
    )
    return ok(
        SummaryOut(
            date=day,
            account_count=account_count,
            total_followers=stat[0],
            new_followers=stat[1],
            views=stat[2],
            likes=stat[3],
            comments=stat[4],
            shares=stat[5],
            published_count=published,
        ).model_dump(mode="json")
    )


@router.get("/export", summary="导出账号日数据 CSV")
async def export_csv(
    user: CurrentUser,
    db: DbDep,
    start: date | None = None,
    end: date | None = None,
):
    start, end = _default_range(end, start)
    rows = (
        await db.execute(
            select(AccountDailyStat, SocialAccount.nickname, SocialAccount.platform)
            .join(SocialAccount, SocialAccount.id == AccountDailyStat.account_id)
            .where(
                AccountDailyStat.team_id == user.team_id,
                AccountDailyStat.date >= start,
                AccountDailyStat.date <= end,
            )
            .order_by(AccountDailyStat.date)
        )
    ).all()

    buf = io.StringIO()
    # Excel 打开中文不乱码
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(["日期", "账号", "平台", "粉丝总量", "新增粉丝", "播放", "点赞", "评论", "分享"])
    for stat, nickname, platform in rows:
        writer.writerow(
            [stat.date, nickname, platform, stat.followers, stat.new_followers, stat.views, stat.likes, stat.comments, stat.shares]
        )
    buf.seek(0)
    filename = f"stats_{start}_{end}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/push-summary", summary="推送昨日汇总到飞书/钉钉 webhook")
async def push_summary(user: CurrentUser, db: DbDep, day: date | None = None):
    team = await db.get(Team, user.team_id)
    if not team.webhook_url:
        raise BizError(400, "团队未配置 webhook，请先在团队设置中填写")
    day = day or (date.today() - timedelta(days=1))
    yesterday = day - timedelta(days=1)

    async def _agg(d: date):
        result = await db.execute(
            select(
                func.coalesce(func.sum(AccountDailyStat.new_followers), 0),
                func.coalesce(func.sum(AccountDailyStat.views), 0),
                func.coalesce(func.sum(AccountDailyStat.likes), 0),
            ).where(AccountDailyStat.team_id == user.team_id, AccountDailyStat.date == d)
        )
        return result.one()

    cur = await _agg(day)
    prev = await _agg(yesterday)

    def _delta(now_v: int, old_v: int) -> str:
        diff = now_v - old_v
        arrow = "↑" if diff >= 0 else "↓"
        return f"{now_v}（环比 {arrow}{abs(diff)}）"

    text = (
        f"【{team.name}】数据日报 {day}\n"
        f"· 新增粉丝：{_delta(cur[0], prev[0])}\n"
        f"· 播放量：{_delta(cur[1], prev[1])}\n"
        f"· 点赞数：{_delta(cur[2], prev[2])}"
    )
    # 飞书/钉钉自定义机器人兼容的 text 消息格式
    payload = {"msg_type": "text", "content": {"text": text}}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(team.webhook_url, json=payload)
        resp.raise_for_status()
    return ok({"pushed": True, "date": day.isoformat(), "text": text})
