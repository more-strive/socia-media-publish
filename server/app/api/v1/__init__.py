from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    ai,
    auth,
    billing,
    contents,
    messages,
    publish,
    proxies,
    stats,
    teams,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(teams.router)
api_router.include_router(users.router)
api_router.include_router(accounts.router)
api_router.include_router(proxies.router)
api_router.include_router(contents.router)
api_router.include_router(publish.router)
api_router.include_router(messages.router)
api_router.include_router(stats.router)
api_router.include_router(ai.router)
api_router.include_router(billing.router)
