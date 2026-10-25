"""Redis 客户端（async）"""
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings

_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def redis_dep() -> AsyncGenerator[aioredis.Redis, None]:
    yield get_redis()


# 常用 key 前缀
KEY_SMS = "sms:{phone}"                    # 短信验证码
KEY_REFRESH_TOKEN = "rt:{user_id}"         # refresh token 白名单
KEY_INVITE = "invite:{code}"               # 团队邀请码
KEY_PUBLISH_QUEUE = "publish:queue"        # 定时发布 zset: {task_id: score=发布时间戳}
KEY_PUBLISH_LOCK = "publish:lock:{task_id}"
KEY_DAILY_PUSH = "push:daily:{date}"       # 当日汇总推送去重
