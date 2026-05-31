from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address)

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": True, "message": f"Rate limit exceeded: {exc.detail}"}
    )

WRITE_LIMIT = "50/hour"        
GENERAL_LIMIT_MIN = "60/minute"  
GENERAL_LIMIT_HOUR = "500/hour" 