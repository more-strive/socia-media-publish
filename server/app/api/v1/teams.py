"""团队管理：信息修改 / 邀请链接 / 加入团队 / 操作日志"""
import secrets

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, PageDep, RedisDep, require_roles
from app.core.exceptions import BizError, NotFoundError
from app.db.redis import KEY_INVITE
from app.models.billing import AuditLog
from app.models.enums import UserRole
from app.models.team import Team, User
from app.schemas.auth import TeamBrief
from app.schemas.common import ok
from app.schemas.team import AuditLogOut, InviteOut, JoinIn, TeamUpdateIn

router = APIRouter(prefix="/teams", tags=["团队"])

INVITE_TTL = 7 * 86400


async def log_action(db, team_id: int, user_id: int, action: str, detail: dict | None = None) -> None:
    db.add(AuditLog(team_id=team_id, user_id=user_id, action=action, detail=detail, created_at=func.now()))


@router.get("/me", summary="团队信息")
async def get_team(user: CurrentUser, db: DbDep):
    team = await db.get(Team, user.team_id)
    member_count = await db.scalar(select(func.count()).select_from(User).where(User.team_id == team.id))
    data = TeamBrief.model_validate(team).model_dump(mode="json")
    data["seats_used"] = member_count
    return ok(data)


@router.put("/me", summary="修改团队设置（名称/审核流/webhook）", dependencies=[require_roles(UserRole.owner, UserRole.admin)])
async def update_team(payload: TeamUpdateIn, user: CurrentUser, db: DbDep):
    team = await db.get(Team, user.team_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(team, field, value)
    await log_action(db, team.id, user.id, "team.update", payload.model_dump(exclude_none=True))
    await db.commit()
    return ok(TeamBrief.model_validate(team).model_dump(mode="json"))


@router.post("/invite", summary="生成邀请链接", dependencies=[require_roles(UserRole.owner, UserRole.admin)])
async def create_invite(user: CurrentUser, redis: RedisDep):
    code = secrets.token_urlsafe(16)
    await redis.set(KEY_INVITE.format(code=code), str(user.team_id), ex=INVITE_TTL)
    return ok(InviteOut(invite_code=code, expire_seconds=INVITE_TTL).model_dump())


@router.post("/join", summary="通过邀请码加入团队")
async def join_team(payload: JoinIn, user: CurrentUser, db: DbDep, redis: RedisDep):
    team_id_raw = await redis.get(KEY_INVITE.format(code=payload.invite_code))
    if team_id_raw is None:
        raise BizError(404, "邀请码无效或已过期")
    team = await db.get(Team, int(team_id_raw))
    if team is None:
        raise NotFoundError("团队不存在")
    member_count = await db.scalar(select(func.count()).select_from(User).where(User.team_id == team.id))
    if member_count >= team.seats_total:
        raise BizError(409, "团队席位已满，请联系管理员扩容")
    user.team_id = team.id
    if user.role == UserRole.owner.value:
        user.role = UserRole.operator.value  # 原 owner 加入新团队后降为普通运营
    await log_action(db, team.id, user.id, "team.join")
    await db.commit()
    return ok(message="加入成功")


@router.get("/logs", summary="操作日志", dependencies=[require_roles(UserRole.owner, UserRole.admin)])
async def team_logs(user: CurrentUser, db: DbDep, page: PageDep):
    total = await db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.team_id == user.team_id)
    )
    rows = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.team_id == user.team_id)
            .order_by(AuditLog.id.desc())
            .offset(page.offset)
            .limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [AuditLogOut.model_validate(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )
