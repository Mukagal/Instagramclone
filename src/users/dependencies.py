from typing import Any, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db.models import User
from ..db.main import get_session
from .UserService import UserService
from .utils import decode_token, is_jti_blocked

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    token = credentials.credentials
    token_data = decode_token(token)

    if not token_data or token_data.get("refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    jti = token_data.get("jti")
    if jti and await is_jti_blocked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again",
        )

    user = await UserService().get_user_by_email(token_data["user"]["email"], session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your account has been banned. Reason: {user.ban_reason or 'Policy violation'}",
        )

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        HTTPBearer(auto_error=False)
    ),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    if not credentials:
        return None
    token_data = decode_token(credentials.credentials)
    if not token_data or token_data.get("refresh"):
        return None
    jti = token_data.get("jti")
    if jti and await is_jti_blocked(jti):
        return None
    return await UserService().get_user_by_email(
        token_data["user"]["email"], session
    )


class RoleChecker:
    """Dependency that restricts an endpoint to users with specific roles."""

    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> Any:
        if current_user.is_staff or current_user.role in self.allowed_roles:
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to perform this action.",
        )


admin_required = RoleChecker(["admin"])
staff_required = RoleChecker(["admin", "staff"])