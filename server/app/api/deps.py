"""通用依赖：当前用户 / 角色权限 / 分页"""
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError, PermissionDeniedError
from app.core.security import decode_token
from app.db.redis import redis_dep
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.team import User

bearer_scheme = HTTPBearer(auto_error=False)

DbDep = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[aioredis.Redis, Depends(redis_dep)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbDep,
) -> User:
    if credentials is None:
        raise BizError(401, "未登录或缺少 token")
    user_id = decode_token(credentials.credentials, expected_type="access")
    if user_id is None:
        raise BizError(401, "token 无效或已过期")
    user = await db.get(User, user_id)
    if user is None or user.status != "active":
        raise BizError(401, "用户不存在或已禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """角色门卫：require_roles(UserRole.admin) / require_roles(UserRole.owner, UserRole.admin)"""

    async def checker(user: CurrentUser) -> User:
        allowed = {r.value for r in roles}
        if user.role not in allowed:
            raise PermissionDeniedError(f"需要角色：{'/'.join(allowed)}")
        return user

    return Depends(checker)


class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


PageDep = Annotated[Pagination, Depends()]
