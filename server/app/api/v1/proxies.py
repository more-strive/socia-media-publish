"""代理 IP 管理：CRUD + 连通性检测（TCP 握手）"""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, PageDep
from app.core.exceptions import NotFoundError
from app.models.account import ProxyIP
from app.models.enums import ProxyStatus
from app.schemas.account import ProxyIn, ProxyOut
from app.schemas.common import ok

router = APIRouter(prefix="/proxies", tags=["代理IP"])


async def _check_tcp(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


@router.get("", summary="代理列表")
async def list_proxies(user: CurrentUser, db: DbDep, page: PageDep):
    conds = [ProxyIP.team_id == user.team_id]
    total = await db.scalar(select(func.count()).select_from(ProxyIP).where(*conds))
    rows = (
        await db.execute(
            select(ProxyIP).where(*conds).order_by(ProxyIP.id.desc()).offset(page.offset).limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [ProxyOut.model_validate(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.post("", summary="新增代理")
async def create_proxy(payload: ProxyIn, user: CurrentUser, db: DbDep):
    proxy = ProxyIP(team_id=user.team_id, **payload.model_dump())
    db.add(proxy)
    await db.commit()
    return ok(ProxyOut.model_validate(proxy).model_dump())


@router.put("/{proxy_id}", summary="修改代理")
async def update_proxy(proxy_id: int, payload: ProxyIn, user: CurrentUser, db: DbDep):
    proxy = await db.scalar(select(ProxyIP).where(ProxyIP.id == proxy_id, ProxyIP.team_id == user.team_id))
    if proxy is None:
        raise NotFoundError("代理不存在")
    for k, v in payload.model_dump().items():
        setattr(proxy, k, v)
    await db.commit()
    return ok(ProxyOut.model_validate(proxy).model_dump())


@router.delete("/{proxy_id}", summary="删除代理")
async def delete_proxy(proxy_id: int, user: CurrentUser, db: DbDep):
    proxy = await db.scalar(select(ProxyIP).where(ProxyIP.id == proxy_id, ProxyIP.team_id == user.team_id))
    if proxy is None:
        raise NotFoundError("代理不存在")
    await db.delete(proxy)
    await db.commit()
    return ok(message="已删除")


@router.post("/{proxy_id}/check", summary="连通性检测")
async def check_proxy(proxy_id: int, user: CurrentUser, db: DbDep):
    proxy = await db.scalar(select(ProxyIP).where(ProxyIP.id == proxy_id, ProxyIP.team_id == user.team_id))
    if proxy is None:
        raise NotFoundError("代理不存在")
    alive = await _check_tcp(proxy.host, proxy.port)
    proxy.status = ProxyStatus.ok.value if alive else ProxyStatus.broken.value
    proxy.last_check_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return ok(ProxyOut.model_validate(proxy).model_dump(), "连通" if alive else "不可达")
