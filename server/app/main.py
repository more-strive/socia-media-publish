"""FastAPI 应用入口

启动：uvicorn app.main:app --reload
文档：/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.redis import close_redis, get_redis
from app.db.session import engine
from app.services.scheduler import recover_stale_tasks, start_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：Redis 预热、崩溃恢复、启动发布调度器
    get_redis()
    try:
        await recover_stale_tasks()
    except Exception:
        logger.warning("崩溃恢复跳过（数据库可能未初始化，可先执行 python -m scripts.init_db）")
    scheduler_task = start_scheduler()
    logger.info("%s 已启动", settings.app_name)
    yield
    # 关闭
    scheduler_task.cancel()
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="社媒矩阵运营中台 Server（一键分发 / AI 创作 / 账号托管 / 私信评论 / 数据统计 / 团队协作 / 订阅计费）",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["系统"])
    async def health():
        """健康检查：MySQL + Redis 连通性"""
        checks = {}
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["mysql"] = "ok"
        except Exception as e:
            checks["mysql"] = f"error: {e}"
        try:
            await get_redis().ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"
        healthy = all(v == "ok" for v in checks.values())
        return {"status": "healthy" if healthy else "degraded", "checks": checks}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
