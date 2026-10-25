"""端到端冒烟测试：不依赖 MySQL，用 SQLite 替身引擎跑通全业务链路（需本机 Redis）

覆盖：注册登录 → 账号托管 → 内容审核流 → 一键分发(调度器) → AI 文案 → 订单支付 → 私信自动回复
用法：python -m scripts.smoke_test
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Windows GBK 控制台兼容
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_FILE = Path(__file__).resolve().parent.parent / ".smoke.db"


def _switch_to_sqlite():
    """把全局引擎换成 SQLite（BigInteger 主键需 variant 成 INTEGER 才能自增）"""
    from sqlalchemy import BigInteger, Integer
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.db.session as session_mod
    from app.models import Base

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, BigInteger) and col.primary_key:
                col.type = col.type.with_variant(Integer(), "sqlite")

    if DB_FILE.exists():
        os.remove(DB_FILE)

    engine = create_async_engine(f"sqlite+aiosqlite:///{DB_FILE}", echo=False)
    session_mod.engine = engine
    session_mod.async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 直接导入了 factory 的模块要逐个替换
    import app.api.v1.ai as ai_mod
    import app.services.scheduler as scheduler_mod

    scheduler_mod.async_session_factory = session_mod.async_session_factory
    ai_mod.async_session_factory = session_mod.async_session_factory
    return engine


PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  [{detail}]" if detail and not cond else ""))


async def main() -> None:
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    engine = _switch_to_sqlite()

    import httpx
    from app.db.redis import KEY_PUBLISH_QUEUE, get_redis
    from app.models import Base
    from app.services.scheduler import dispatch_due_tasks

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 预置套餐（正式环境由 init_db 提供）
    from app.db.session import async_session_factory
    from app.models.billing import Plan

    async with async_session_factory() as db:
        db.add_all([
            Plan(code="free", name="免费版", price_monthly=0, price_yearly=0, features=["基础功能"]),
            Plan(code="pro", name="专业版", price_monthly=299, price_yearly=2990, credits_monthly=1000),
            Plan(code="team", name="团队版", price_monthly=899, price_yearly=8990, credits_monthly=5000),
        ])
        await db.commit()

    redis = get_redis()
    await redis.delete(KEY_PUBLISH_QUEUE)

    base = "http://test/api/v1"
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=base) as c:
        # ---- 1. 注册 / 登录 ----
        r = (await c.post("/auth/register", json={
            "phone": "13900001111", "password": "pass12345678",
            "nickname": "测试老板", "team_name": "冒烟测试团队",
        })).json()
        check("注册返回 token", r["code"] == 0 and r["data"]["access_token"])
        token = r["data"]["access_token"]
        H = {"Authorization": f"Bearer {token}"}

        r = (await c.get("/auth/me", headers=H)).json()
        check("获取 me", r["code"] == 0 and r["data"]["user"]["role"] == "owner")

        # ---- 2. 账号托管 ----
        r = (await c.post("/accounts/groups", headers=H, json={"name": "主力组"})).json()
        group_id = r["data"]["id"]
        account_ids = []
        for platform, nick in [("douyin", "冒烟抖音号"), ("xhs", "冒烟小红书号")]:
            r = (await c.post("/accounts", headers=H, json={
                "platform": platform, "nickname": nick, "group_id": group_id, "fans_count": 1000,
            })).json()
            account_ids.append(r["data"]["id"])
        check("新增 2 个托管账号", all(account_ids))
        r = (await c.get("/accounts", headers=H, params={"platform": "douyin"})).json()
        check("账号列表筛选", r["code"] == 0 and r["data"]["total"] == 1)

        # ---- 3. 内容 + 审核流 ----
        r = (await c.post("/contents", headers=H, json={
            "type": "video", "title": "冒烟测试视频", "media": ["https://cdn.example.com/v.mp4"],
            "tags": ["测试"],
        })).json()
        content_id = r["data"]["id"]
        r = (await c.post(f"/contents/{content_id}/submit", headers=H)).json()
        check("内容提交审核", r["code"] == 0)
        r = (await c.post(f"/contents/{content_id}/review", headers=H, json={"approve": True})).json()
        check("内容审核通过", r["code"] == 0)

        # ---- 4. 一键分发：即时发布走调度器 ----
        r = (await c.post("/publish/tasks", headers=H, json={
            "content_id": content_id, "account_ids": account_ids, "mode": "immediate",
        })).json()
        check("创建发布任务", r["code"] == 0 and r["data"]["item_count"] == 2)
        task_id = r["data"]["id"]
        await dispatch_due_tasks()
        await asyncio.sleep(1.5)  # 等待后台协程完成 mock 发布
        r = (await c.get(f"/publish/tasks/{task_id}", headers=H)).json()
        data = r["data"]
        check(
            "调度器完成发布",
            data["status"] == "published" and data["success_count"] == 2,
            f"status={data['status']} success={data['success_count']}",
        )

        # ---- 5. 定时发布入队 + 取消 ----
        from datetime import datetime, timedelta, timezone

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        r = (await c.post("/publish/tasks", headers=H, json={
            "content_id": content_id, "account_ids": account_ids, "mode": "scheduled", "scheduled_at": future,
        })).json()
        scheduled_id = r["data"]["id"]
        queued = await redis.zcard(KEY_PUBLISH_QUEUE)
        check("定时任务入队 zset", queued == 1)
        r = (await c.post(f"/publish/tasks/{scheduled_id}/cancel", headers=H)).json()
        check("取消定时任务", r["code"] == 0 and (await redis.zcard(KEY_PUBLISH_QUEUE)) == 0)

        # ---- 6. 发布日历 ----
        r = (await c.get("/publish/calendar", headers=H, params={
            "start": (datetime.utcnow() - timedelta(days=1)).date().isoformat(),
            "end": (datetime.utcnow() + timedelta(days=1)).date().isoformat(),
        })).json()
        check("发布日历", r["code"] == 0 and len(r["data"]) >= 1)

        # ---- 7. AI 文案（积分计费）----
        credits_before = (await c.get("/ai/credits", headers=H)).json()["data"]["credits"]
        r = (await c.post("/ai/tasks", headers=H, json={"task_type": "copy", "prompt": "无线耳机推荐"})).json()
        check("AI 文案生成", r["code"] == 0 and r["data"]["status"] == "succeeded" and r["data"]["result"]["text"])
        credits_after = (await c.get("/ai/credits", headers=H)).json()["data"]["credits"]
        check("积分扣减", credits_before - credits_after == 1)

        # ---- 8. 订单 + mock 支付 ----
        r = (await c.get("/billing/plans")).json()
        plan_id = r["data"][0]["id"]
        r = (await c.post("/billing/orders", headers=H, json={"type": "new", "plan_id": plan_id, "quantity": 3})).json()
        order_id = r["data"]["id"]
        check("创建订单", r["code"] == 0 and r["data"]["status"] == "unpaid")
        r = (await c.post(f"/billing/orders/{order_id}/mock-pay", headers=H)).json()
        check("mock 支付生效", r["code"] == 0 and r["data"]["status"] == "paid")
        r = (await c.get("/billing/subscription", headers=H)).json()
        check("订阅信息", r["code"] == 0 and r["data"]["plan"] is not None)

        # ---- 9. 私信评论 + 自动回复 ----
        r = (await c.post("/messages/reply-rules", headers=H, json={
            "rule_type": "keyword", "keywords": ["价格"], "content": "亲，链接在主页橱窗～",
        })).json()
        check("创建自动回复规则", r["code"] == 0)
        r = (await c.post("/messages/mock/inbound", headers=H, json={
            "account_id": account_ids[0], "msg_type": "dm", "content": "请问价格多少？", "from_name": "买家A",
        })).json()
        check("模拟入站私信", r["code"] == 0)
        r = (await c.get("/messages", headers=H, params={"msg_type": "dm"})).json()
        outbound = [m for m in r["data"]["items"]]  # 列表仅含 inbound；自动回复出站消息需从回复接口验证
        check("收件箱列表", r["code"] == 0 and len(outbound) == 1)

        # 入站消息回复
        r = (await c.post(f"/messages/{outbound[0]['id']}/reply", headers=H, json={"content": "已私聊"})).json()
        check("人工回复私信", r["code"] == 0 and r["data"]["direction"] == "outbound")

        # 自动回复是否落库（直接查库验证）
        from sqlalchemy import select
        from app.db.session import async_session_factory
        from app.models.interaction import Message

        async with async_session_factory() as db:
            rows = (await db.execute(
                select(Message).where(Message.auto_reply.is_(True))
            )).scalars().all()
        check("关键词命中自动回复", len(rows) == 1 and "橱窗" in rows[0].content)

        # ---- 10. 团队邀请 / 成员 ----
        r = (await c.post("/teams/invite", headers=H)).json()
        invite_code = r["data"]["invite_code"]
        r2 = (await c.post("/auth/register", json={
            "phone": "13900002222", "password": "pass12345678",
            "nickname": "新成员", "team_name": "临时团队",
        })).json()
        h2 = {"Authorization": f"Bearer {r2['data']['access_token']}"}
        r = (await c.post("/teams/join", headers=h2, json={"invite_code": invite_code})).json()
        check("邀请码加入团队", r["code"] == 0)

        # ---- 11. 权限：operator 需任务审核 ----
        from app.models.enums import UserRole
        from app.models.team import User as UserModel

        async with async_session_factory() as db:
            newbie = await db.scalar(select(UserModel).where(UserModel.phone == "13900002222"))
            newbie.role = UserRole.operator.value
            await db.commit()
        r = (await c.post("/publish/tasks", headers=h2, json={
            "content_id": content_id, "account_ids": [account_ids[0]], "mode": "immediate",
        })).json()
        check("operator 任务进入审核", r["code"] == 0 and r["data"]["status"] == "reviewing")
        review_task_id = r["data"]["id"]
        r = (await c.post(f"/publish/tasks/{review_task_id}/review", headers=H, json={"approve": True})).json()
        await dispatch_due_tasks()
        await asyncio.sleep(1.0)
        r = (await c.get(f"/publish/tasks/{review_task_id}", headers=h2)).json()
        check("审核通过后发布完成", r["data"]["status"] == "published")

        # ---- 12. 代理 IP（本机 Redis 端口做连通性检测）----
        r = (await c.post("/proxies", headers=H, json={
            "name": "本地代理", "scheme": "http", "host": "127.0.0.1", "port": 6379, "region": "本机",
        })).json()
        proxy_id = r["data"]["id"]
        r = (await c.post(f"/proxies/{proxy_id}/check", headers=H)).json()
        check("代理连通性检测", r["code"] == 0 and r["data"]["status"] == "ok", str(r))

        # ---- 13. 话术库 ----
        r = (await c.post("/messages/scripts", headers=H, json={"title": "开场白", "content": "您好～"})).json()
        check("新建话术", r["code"] == 0)
        r = (await c.get("/messages/scripts", headers=H)).json()
        check("话术列表", r["code"] == 0 and len(r["data"]) == 1)

        # ---- 14. 统计明细 / 导出 ----
        r = (await c.get("/stats/accounts", headers=H)).json()
        check("账号时序数据", r["code"] == 0 and len(r["data"]) == 2)
        r = (await c.get("/stats/contents", headers=H)).json()
        check("作品排行", r["code"] == 0 and isinstance(r["data"], list))
        resp = await c.get("/stats/export", headers=H)
        check("CSV 导出", resp.status_code == 200 and "日期" in resp.text)
        r = (await c.get("/stats/summary", headers=H)).json()
        check("团队汇总", r["code"] == 0 and r["data"]["account_count"] == 2)

    print(f"\n{'='*40}\n通过 {len(PASS)} / {len(PASS)+len(FAIL)}")
    if FAIL:
        print("失败项：", FAIL)
        sys.exit(1)
    if DB_FILE.exists():
        os.remove(DB_FILE)


if __name__ == "__main__":
    asyncio.run(main())
