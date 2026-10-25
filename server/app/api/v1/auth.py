"""认证：注册 / 密码登录 / 短信验证码登录 / 刷新 / 登出"""
import random

from fastapi import APIRouter
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbDep, RedisDep
from app.core.config import settings
from app.core.exceptions import BizError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.redis import KEY_REFRESH_TOKEN, KEY_SMS
from app.models.enums import UserRole
from app.models.team import Team, User
from app.schemas.auth import (
    MeOut,
    PasswordLoginIn,
    RefreshIn,
    RegisterIn,
    SmsLoginIn,
    SmsSendIn,
    TeamBrief,
    TokenOut,
    UserOut,
)
from app.schemas.common import ok

router = APIRouter(prefix="/auth", tags=["认证"])


def _tokens(user_id: int) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def _whitelist_refresh(redis, tokens: TokenOut, user_id: int) -> None:
    await redis.set(
        KEY_REFRESH_TOKEN.format(user_id=user_id),
        tokens.refresh_token,
        ex=settings.refresh_token_expire_days * 86400,
    )


@router.post("/register", summary="注册（自动创建团队并成为 owner）")
async def register(payload: RegisterIn, db: DbDep, redis: RedisDep):
    # 唯一性检查
    conds = []
    if payload.phone:
        conds.append(User.phone == payload.phone)
    if payload.email:
        conds.append(User.email == payload.email)
    exists = await db.scalar(select(func.count()).select_from(User).where(or_(*conds)))
    if exists:
        raise BizError(409, "手机号或邮箱已被注册")

    team = Team(name=payload.team_name)
    db.add(team)
    await db.flush()
    user = User(
        team_id=team.id,
        phone=payload.phone,
        email=payload.email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
        role=UserRole.owner.value,
    )
    db.add(user)
    await db.commit()
    tokens = _tokens(user.id)
    await _whitelist_refresh(redis, tokens, user.id)
    return ok(tokens, "注册成功")


@router.post("/login", summary="密码登录")
async def password_login(payload: PasswordLoginIn, db: DbDep, redis: RedisDep):
    user = await db.scalar(
        select(User).where(or_(User.phone == payload.account, User.email == payload.account))
    )
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise BizError(401, "账号或密码错误")
    if user.status != "active":
        raise BizError(403, "账号已禁用")
    user.last_login_at = func.now()
    await db.commit()
    tokens = _tokens(user.id)
    # refresh token 白名单（登出时删除）
    await _whitelist_refresh(redis, tokens, user.id)
    return ok(tokens)


@router.post("/sms/send", summary="发送短信验证码（mock：写 Redis）")
async def send_sms(payload: SmsSendIn, redis: RedisDep):
    code = f"{random.randint(0, 999999):06d}"
    await redis.set(KEY_SMS.format(phone=payload.phone), code, ex=300)
    data = {"expire_seconds": 300}
    if settings.dev_return_sms_code:
        data["code"] = code  # 仅开发环境回显
    return ok(data, "验证码已发送")


@router.post("/sms/login", summary="验证码登录（未注册自动建号）")
async def sms_login(payload: SmsLoginIn, db: DbDep, redis: RedisDep):
    cached = await redis.get(KEY_SMS.format(phone=payload.phone))
    if cached is None or cached != payload.code:
        raise BizError(401, "验证码错误或已过期")
    await redis.delete(KEY_SMS.format(phone=payload.phone))

    user = await db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        team = Team(name=f"{payload.phone}的团队")
        db.add(team)
        await db.flush()
        user = User(
            team_id=team.id,
            phone=payload.phone,
            nickname=f"用户{payload.phone[-4:]}",
            role=UserRole.owner.value,
        )
        db.add(user)
    user.last_login_at = func.now()
    await db.commit()
    tokens = _tokens(user.id)
    await _whitelist_refresh(redis, tokens, user.id)
    return ok(tokens)


@router.post("/refresh", summary="刷新 access token")
async def refresh(payload: RefreshIn, db: DbDep, redis: RedisDep):
    user_id = decode_token(payload.refresh_token, expected_type="refresh")
    if user_id is None:
        raise BizError(401, "refresh token 无效或已过期")
    whitelisted = await redis.get(KEY_REFRESH_TOKEN.format(user_id=user_id))
    if whitelisted != payload.refresh_token:
        raise BizError(401, "refresh token 已失效，请重新登录")
    user = await db.get(User, user_id)
    if user is None or user.status != "active":
        raise BizError(401, "用户不可用")
    return ok(_tokens(user.id))


@router.post("/logout", summary="登出（吊销 refresh token）")
async def logout(user: CurrentUser, redis: RedisDep):
    await redis.delete(KEY_REFRESH_TOKEN.format(user_id=user.id))
    return ok(message="已登出")


@router.get("/me", summary="当前用户与团队信息", response_model=None)
async def me(user: CurrentUser, db: DbDep) -> dict:
    team = await db.get(Team, user.team_id)
    return ok(
        MeOut(user=UserOut.model_validate(user), team=TeamBrief.model_validate(team)).model_dump(mode="json")
    )
