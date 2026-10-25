"""业务异常与统一响应"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class BizError(Exception):
    """业务异常：code 会透出给前端，message 直接可展示"""

    def __init__(self, code: int = 400, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(BizError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(404, message)


class PermissionDeniedError(BizError):
    def __init__(self, message: str = "无权限执行该操作"):
        super().__init__(403, message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def biz_error_handler(_: Request, exc: BizError):
        return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        msg = first.get("msg", "参数错误")
        return JSONResponse(
            status_code=200,
            content={"code": 422, "message": f"{loc}: {msg}" if loc else msg, "data": None},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, __: IntegrityError):
        return JSONResponse(status_code=200, content={"code": 409, "message": "数据冲突，请检查唯一性字段", "data": None})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception):
        from app.core.config import settings

        detail = str(exc) if settings.debug else "服务器内部错误"
        return JSONResponse(status_code=200, content={"code": 500, "message": detail, "data": None})
