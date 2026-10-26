"""账号托管：多平台账号 CRUD / 分组 / 失效检测 / 重新授权"""
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbDep, PageDep, require_roles
from app.core.exceptions import BizError, NotFoundError
from app.models.account import AccountGroup, SocialAccount
from app.models.enums import AuthStatus, UserRole
from app.schemas.account import (
    AccountGroupIn,
    AccountGroupOut,
    AccountIn,
    AccountOut,
    AccountUpdateIn,
    BatchCheckOut,
)
from app.schemas.common import ok

router = APIRouter(prefix="/accounts", tags=["账号托管"])


def _out(a: SocialAccount) -> dict:
    data = AccountOut.model_validate(a).model_dump(mode="json")
    data["group_name"] = a.group.name if a.group else None
    return data


# ---------- 分组 ----------


@router.get("/groups", summary="账号分组列表")
async def list_groups(user: CurrentUser, db: DbDep):
    rows = (
        await db.execute(
            select(AccountGroup).where(AccountGroup.team_id == user.team_id).order_by(AccountGroup.sort)
        )
    ).scalars().all()
    return ok([AccountGroupOut.model_validate(r).model_dump() for r in rows])


@router.post("/groups", summary="新建分组")
async def create_group(payload: AccountGroupIn, user: CurrentUser, db: DbDep):
    group = AccountGroup(team_id=user.team_id, **payload.model_dump())
    db.add(group)
    await db.commit()
    return ok(AccountGroupOut.model_validate(group).model_dump())


@router.put("/groups/{group_id}", summary="修改分组")
async def update_group(group_id: int, payload: AccountGroupIn, user: CurrentUser, db: DbDep):
    group = await db.scalar(
        select(AccountGroup).where(AccountGroup.id == group_id, AccountGroup.team_id == user.team_id)
    )
    if group is None:
        raise NotFoundError("分组不存在")
    for k, v in payload.model_dump().items():
        setattr(group, k, v)
    await db.commit()
    return ok(AccountGroupOut.model_validate(group).model_dump())


@router.delete("/groups/{group_id}", summary="删除分组（账号移回未分组）")
async def delete_group(group_id: int, user: CurrentUser, db: DbDep):
    group = await db.scalar(
        select(AccountGroup).where(AccountGroup.id == group_id, AccountGroup.team_id == user.team_id)
    )
    if group is None:
        raise NotFoundError("分组不存在")
    await db.execute(update(SocialAccount).where(SocialAccount.group_id == group_id).values(group_id=None))
    await db.delete(group)
    await db.commit()
    return ok(message="已删除")


# ---------- 账号 ----------


@router.get("", summary="账号列表（按平台/分组/授权状态筛选）")
async def list_accounts(
    user: CurrentUser,
    db: DbDep,
    page: PageDep,
    platform: str | None = None,
    group_id: int | None = None,
    auth_status: str | None = None,
    keyword: str | None = None,
):
    conds = [SocialAccount.team_id == user.team_id]
    if platform:
        conds.append(SocialAccount.platform == platform)
    if group_id:
        conds.append(SocialAccount.group_id == group_id)
    if auth_status:
        conds.append(SocialAccount.auth_status == auth_status)
    if keyword:
        conds.append(SocialAccount.nickname.like(f"%{keyword}%"))

    total = await db.scalar(select(func.count()).select_from(SocialAccount).where(*conds))
    rows = (
        await db.execute(
            select(SocialAccount)
            .where(*conds)
            .order_by(SocialAccount.id.desc())
            .offset(page.offset)
            .limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [_out(r) for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.post("", summary="新增托管账号（mock 授权）")
async def create_account(payload: AccountIn, user: CurrentUser, db: DbDep):
    if payload.group_id:
        group = await db.scalar(
            select(AccountGroup).where(AccountGroup.id == payload.group_id, AccountGroup.team_id == user.team_id)
        )
        if group is None:
            raise BizError(404, "分组不存在")
    account = SocialAccount(
        team_id=user.team_id,
        auth_payload=hashlib.sha256(f"mock:{user.team_id}:{payload.nickname}".encode()).hexdigest(),
        **payload.model_dump(),
    )
    db.add(account)
    await db.commit()
    return ok(AccountOut.model_validate(account).model_dump(mode="json"))


@router.put("/{account_id}", summary="更新账号（分组/运营人/代理/区域）")
async def update_account(account_id: int, payload: AccountUpdateIn, user: CurrentUser, db: DbDep):
    account = await db.scalar(
        select(SocialAccount).where(SocialAccount.id == account_id, SocialAccount.team_id == user.team_id)
    )
    if account is None:
        raise NotFoundError("账号不存在")
    # exclude_unset：仅覆盖客户端显式传入的字段（传 null 即清空代理/分组等可空关联）
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(account, k, v)
    await db.commit()
    return ok(_out(account))


@router.delete("/{account_id}", summary="删除账号", dependencies=[require_roles(UserRole.owner, UserRole.admin)])
async def delete_account(account_id: int, user: CurrentUser, db: DbDep):
    account = await db.scalar(
        select(SocialAccount).where(SocialAccount.id == account_id, SocialAccount.team_id == user.team_id)
    )
    if account is None:
        raise NotFoundError("账号不存在")
    await db.delete(account)
    await db.commit()
    return ok(message="已删除")


@router.post("/batch-check", summary="批量检测账号有效性（失效一键识别）", response_model=None)
async def batch_check(user: CurrentUser, db: DbDep):
    rows = (
        await db.execute(select(SocialAccount).where(SocialAccount.team_id == user.team_id))
    ).scalars().all()
    expired = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for a in rows:
        # mock 检测：以账号 id 做确定性伪随机，约 10% 判定失效
        h = int(hashlib.md5(f"chk:{a.id}".encode()).hexdigest(), 16) % 100
        a.last_active_at = now
        if a.auth_payload is None:
            a.auth_status = AuthStatus.expired.value
        elif h < 10:
            a.auth_status = AuthStatus.expired.value
        else:
            a.auth_status = AuthStatus.valid.value
        if a.auth_status == AuthStatus.expired.value:
            expired += 1
    await db.commit()
    return ok(BatchCheckOut(total=len(rows), expired=expired).model_dump())


@router.post("/{account_id}/re-auth", summary="重新授权（mock：直接恢复有效）")
async def re_auth(account_id: int, user: CurrentUser, db: DbDep):
    account = await db.scalar(
        select(SocialAccount).where(SocialAccount.id == account_id, SocialAccount.team_id == user.team_id)
    )
    if account is None:
        raise NotFoundError("账号不存在")
    account.auth_payload = hashlib.sha256(
        f"mock:{user.team_id}:{account.nickname}:re".encode()
    ).hexdigest()
    account.auth_status = AuthStatus.valid.value
    await db.commit()
    return ok(message="已重新授权")
