"""建库建表 + 演示数据

用法：python -m scripts.init_db
- 开发环境直接 create_all；生产建议走 alembic 迁移
- 会写入演示团队/用户/账号/近 30 天统计数据，便于联调前端
"""
import asyncio
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import Base, async_session_factory, engine
from app.models import (
    AccountDailyStat,
    AccountGroup,
    Content,
    Plan,
    PublishItem,
    PublishTask,
    Script,
    SocialAccount,
    Team,
    User,
)
from app.models.enums import ContentStatus, PublishItemStatus, PublishTaskStatus
from app.models.interaction import ReplyRule

random.seed(42)

DEMO_PASSWORD = "demo123456"

PLANS = [
    dict(code="free", name="免费版", seats=3, accounts=10, credits_monthly=100, price_monthly=0, price_yearly=0,
         features=["10 个账号托管", "基础数据统计"]),
    dict(code="pro", name="专业版", seats=10, accounts=50, credits_monthly=1000, price_monthly=299, price_yearly=2990,
         features=["50 个账号托管", "定时发布/发布日历", "私信评论管理", "1000 AI 积分/月"]),
    dict(code="team", name="团队版", seats=30, accounts=200, credits_monthly=5000, price_monthly=899, price_yearly=8990,
         features=["200 个账号托管", "审核流与角色权限", "汇总数据推送", "5000 AI 积分/月"]),
]

ACCOUNTS = [
    ("douyin", "数码老王", 128000), ("douyin", "老王的日常", 56000),
    ("xhs", "王姐种草日记", 89000), ("xhs", "性价比研究所", 45000),
    ("shipinhao", "数码老王视频号", 21000), ("kuaishou", "老王快说", 33000),
    ("bilibili", "老王拆机室", 67000), ("wechat_gzh", "数码观察报", 15000),
    ("weibo", "数码老王微博", 40000), ("toutiao", "老王说数码", 26000),
]


async def seed() -> None:
    async with async_session_factory() as db:
        # 套餐
        plans: dict[str, Plan] = {}
        for p in PLANS:
            plan = await db.scalar(select(Plan).where(Plan.code == p["code"]))
            if plan is None:
                plan = Plan(**p)
                db.add(plan)
                await db.flush()
            plans[p["code"]] = plan

        if await db.scalar(select(Team).where(Team.name == "演示团队")):
            print("演示数据已存在，跳过")
            return

        # 团队 + 成员
        team = Team(name="演示团队", plan_id=plans["pro"].id, seats_total=10, credits=5000,
                    plan_expire_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30))
        db.add(team)
        await db.flush()
        owner = User(team_id=team.id, phone="13800000001", password_hash=hash_password(DEMO_PASSWORD),
                     nickname="王老板", role="owner")
        operator = User(team_id=team.id, phone="13800000002", password_hash=hash_password(DEMO_PASSWORD),
                        nickname="小运营", role="operator")
        auditor = User(team_id=team.id, phone="13800000003", password_hash=hash_password(DEMO_PASSWORD),
                       nickname="审核员小张", role="auditor")
        db.add_all([owner, operator, auditor])
        await db.flush()

        # 账号分组 + 托管账号
        g_main = AccountGroup(team_id=team.id, name="主力号")
        g_test = AccountGroup(team_id=team.id, name="测试号", sort=1)
        db.add_all([g_main, g_test])
        await db.flush()

        accounts: list[SocialAccount] = []
        for i, (platform, nickname, fans) in enumerate(ACCOUNTS):
            a = SocialAccount(
                team_id=team.id,
                group_id=g_main.id if i < 6 else g_test.id,
                platform=platform,
                nickname=nickname,
                platform_account_id=f"{platform}_{1000 + i}",
                fans_count=fans,
                auth_payload=f"mock-token-{i}",
                operator_id=owner.id,
            )
            accounts.append(a)
        db.add_all(accounts)
        await db.flush()

        # 内容 + 一个已完成的发布任务
        content = Content(
            team_id=team.id, creator_id=operator.id, type="video",
            title="2026 最值得买的三款耳机", summary="百元到千元全价位推荐",
            media=["https://cdn.example.com/video/earbuds2026.mp4"],
            cover="https://cdn.example.com/cover/earbuds2026.jpg",
            tags=["数码", "耳机"], status=ContentStatus.approved.value,
        )
        db.add(content)
        await db.flush()
        task = PublishTask(team_id=team.id, content_id=content.id, creator_id=operator.id,
                           mode="immediate", status=PublishTaskStatus.published.value)
        db.add(task)
        await db.flush()
        items: list[PublishItem] = []
        for a in accounts[:4]:
            item = PublishItem(
                task_id=task.id, account_id=a.id, status=PublishItemStatus.success.value,
                platform_publish_id=f"{a.platform}-demo-001", publish_url=f"https://mock.{a.platform}.com/p/demo001",
                published_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3),
            )
            items.append(item)
        db.add_all(items)
        await db.flush()

        # 近 30 天账号日统计（带增长趋势，便于画图）
        today = date.today()
        stat_rows = []
        for a in accounts:
            base_followers = a.fans_count - 30 * random.randint(50, 300)
            for d in range(30):
                day = today - timedelta(days=29 - d)
                base_followers += random.randint(20, 400)
                stat_rows.append(AccountDailyStat(
                    account_id=a.id, team_id=team.id, date=day,
                    followers=base_followers,
                    new_followers=random.randint(5, 120),
                    views=random.randint(2000, 80000),
                    likes=random.randint(100, 6000),
                    comments=random.randint(10, 500),
                    shares=random.randint(5, 300),
                ))
        db.add_all(stat_rows)

        # 自动回复规则 + 话术
        db.add(ReplyRule(team_id=team.id, rule_type="keyword",
                         keywords=["价格", "多少钱", "链接"], content="宝子，产品链接在主页橱窗，现在下单有优惠哦～"))
        db.add(ReplyRule(team_id=team.id, rule_type="welcome",
                         content="欢迎关注！回复「价格」查看产品链接～"))
        db.add_all([
            Script(team_id=team.id, group_name="售前", title="开场白", content="您好，请问想了解哪款产品呢？"),
            Script(team_id=team.id, group_name="售后", title="物流查询", content="亲，麻烦提供下订单号，帮您查物流～"),
        ])

        await db.commit()
        print(f"初始化完成。演示账号：13800000001 / {DEMO_PASSWORD}（owner）、13800000002（operator）、13800000003（auditor）")


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("数据表已创建/校验")
    await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
