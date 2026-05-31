from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


ERROR_CODE_BY_STATUS = {
    400: 40001,
    401: 40101,
    404: 40401,
    500: 50001,
    503: 50004,
    504: 50003,
}


def envelope(data=None, message: str = "ok", code: int = 0) -> dict:
    return {"code": code, "data": data, "message": message}


def error_code_for_status(status_code: int) -> int:
    return ERROR_CODE_BY_STATUS.get(status_code, status_code)


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=envelope(
            data=None,
            message=str(exc.detail),
            code=error_code_for_status(exc.status_code),
        ),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in first_error.get("loc", []) if part != "query")
    detail = first_error.get("msg", "参数不合法")
    message = f"参数校验失败: {field} {detail}".strip()
    return JSONResponse(
        status_code=422,
        content=envelope(data=None, message=message, code=40001),
    )


async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=envelope(data=None, message="服务内部错误", code=50001),
    )
