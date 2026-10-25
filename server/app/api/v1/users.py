"""成员管理：列表 / 角色调整 / 移除 / 个人资料"""
from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, PageDep, require_roles
from app.core.exceptions import BizError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.team import User
from app.schemas.auth import UserOut
from app.schemas.common import ok
from app.schemas.team import MemberRoleIn, UserUpdateIn

router = APIRouter(prefix="/users", tags=["成员"])


@router.get("", summary="成员列表")
async def list_users(user: CurrentUser, db: DbDep, page: PageDep):
    total = await db.scalar(select(func.count()).select_from(User).where(User.team_id == user.team_id))
    rows = (
        await db.execute(
            select(User)
            .where(User.team_id == user.team_id)
            .order_by(User.id)
            .offset(page.offset)
            .limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [UserOut.model_validate(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.get("/me", summary="个人信息")
async def get_me(user: CurrentUser):
    return ok(UserOut.model_validate(user).model_dump(mode="json"))


@router.put("/me", summary="修改个人信息")
async def update_me(payload: UserUpdateIn, user: CurrentUser, db: DbDep):
    data = payload.model_dump(exclude_none=True)
    if "password" in data:
        data["password_hash"] = hash_password(data.pop("password"))
    for field, value in data.items():
        setattr(user, field, value)
    await db.commit()
    return ok(UserOut.model_validate(user).model_dump(mode="json"))


@router.put("/{user_id}/role", summary="调整成员角色", dependencies=[require_roles(UserRole.owner, UserRole.admin)])
async def update_role(user_id: int, payload: MemberRoleIn, user: CurrentUser, db: DbDep):
    target = await db.get(User, user_id)
    if target is None or target.team_id != user.team_id:
        raise NotFoundError("成员不存在")
    if target.role == UserRole.owner.value:
        raise PermissionDeniedError("不能修改创建者角色")
    target.role = payload.role
    await db.commit()
    return ok(message="已更新")


@router.delete("/{user_id}", summary="移除成员", dependencies=[require_roles(UserRole.owner, UserRole.admin)])
async def remove_user(user_id: int, user: CurrentUser, db: DbDep):
    target = await db.get(User, user_id)
    if target is None or target.team_id != user.team_id:
        raise NotFoundError("成员不存在")
    if target.role == UserRole.owner.value:
        raise PermissionDeniedError("不能移除创建者")
    if target.id == user.id:
        raise BizError(400, "不能移除自己")
    await db.delete(target)
    await db.commit()
    return ok(message="已移除")
