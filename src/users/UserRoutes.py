import io
import secrets
import base64
from datetime import timedelta
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request,
    File, UploadFile, status,
)
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import Config
from ..db.main import get_session
from ..db.models import User, Follow, FollowStatusEnum

from ..middleware.rate_limit import limiter, WRITE_LIMIT, GENERAL_LIMIT_MIN
from ..tasks.image_task import compress_and_store_image
from ..tasks.mail_task import send_password_reset_email
from ..tasks.moderation_task import moderate_profile_image
from .dependencies import RoleChecker, admin_required, get_current_user, get_optional_user
from ..users.UserSchemas import (
    AccessTokenResponse,
    ForgotPasswordRequest,
    PasswordReset,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserMe,
    UserProfileUpdate,
    UserPublic,
    UserSafe,
    UserUpdate,
)
from ..users.UserService import UserService
from ..users.utils import (
    add_jti_to_blocklist,
    create_access_token,
    decode_token,
    is_jti_blocked,
    verify_password,
)

user_router = APIRouter()
user_service = UserService()
security = HTTPBearer()


@user_router.post("/signup", response_model=UserMe, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_LIMIT)
async def signup(
    request: Request,
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    """Register a new account. Sends a verification email automatically."""
    new_user = await user_service.create_user(user_data, session)
    return new_user


@user_router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(
    request: Request,
    login_data: UserLogin,
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.get_user_by_email(login_data.email, session)

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid email or password",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your account has been banned. Reason: {user.ban_reason or 'Policy violation'}",
        )

    access_token = create_access_token(
        user_data={"email": user.email, "user_id": str(user.id)}
    )
    refresh_token = create_access_token(
        user_data={"email": user.email, "user_id": str(user.id)},
        refresh=True,
        expiry=timedelta(days=Config.REFRESH_TOKEN_EXPIRY),
    )
    return {
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }


@user_router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token_data = decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    jti = token_data.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Token has no jti")
    await add_jti_to_blocklist(jti)
    return {"message": "Logged out successfully"}


@user_router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_access_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token_data = decode_token(credentials.credentials)
    if not token_data or not token_data.get("refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide a valid refresh token",
        )
    jti = token_data.get("jti")
    if jti and await is_jti_blocked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )
    return {"access_token": create_access_token(user_data=token_data["user"])}



@user_router.get("/verify-email")
async def verify_email(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(User).where(User.verification_token == token))
    user = result.first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    user.is_verified = True
    user.verification_token = None
    await session.commit()
    return {"message": "Email verified successfully"}


@user_router.post("/forgot-password")
@limiter.limit(WRITE_LIMIT)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.get_user_by_email(body.email, session)
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_password_token = token
        await session.commit()
        send_password_reset_email.delay(user.email, token)
    return {"message": "If that email exists, a reset link has been sent"}


@user_router.post("/reset-password")
async def reset_password(
    data: PasswordReset,
    session: AsyncSession = Depends(get_session),
):
    from ..users.utils import generate_password_hash

    result = await session.exec(
        select(User).where(User.reset_password_token == data.token)
    )
    user = result.first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    user.password_hash = generate_password_hash(data.new_password)
    user.reset_password_token = None
    await session.commit()
    return {"message": "Password reset successfully"}


@user_router.get("/users/me", response_model=UserMe)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@user_router.patch("/users/me", response_model=UserMe)
@limiter.limit(WRITE_LIMIT)
async def update_me(
    request: Request,
    update_data: UserUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    user = await user_service.update_user(current_user.id, update_data, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@user_router.patch("/users/me/profile", response_model=UserMe)
@limiter.limit(WRITE_LIMIT)
async def update_my_profile(
    request: Request,
    update_data: UserProfileUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update bio, website, gender and other profile-page fields."""
    user = await user_service.update_profile(current_user.id, update_data, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@user_router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_LIMIT)
async def delete_me(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    deleted = await user_service.delete_user(current_user.id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")



@user_router.post("/users/me/avatar", response_model=UserMe)
@limiter.limit(WRITE_LIMIT)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    file.file = io.BytesIO(image_bytes)

    user = await user_service.upload_avatar(current_user.id, file, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    b64 = base64.b64encode(image_bytes).decode()
    moderate_profile_image.delay(current_user.id, b64, Config.DATABASE_URL)

    return user


@user_router.post("/users/me/avatar/compressed", response_model=UserMe)
@limiter.limit(WRITE_LIMIT)
async def upload_avatar_compressed(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upload avatar — compression & moderation run in background tasks."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    b64 = base64.b64encode(image_bytes).decode()

    compress_and_store_image.delay(current_user.id, b64, Config.DATABASE_URL)
    moderate_profile_image.delay(current_user.id, b64, Config.DATABASE_URL)

    return current_user


@user_router.get("/users/{user_id}/avatar")
async def get_avatar(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.get_user(user_id, session)
    if not user or not user.profile or not user.profile.avatar_path:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return RedirectResponse(url=user.profile.avatar_path)


@user_router.get("/users", response_model=List[UserSafe])
async def search_users(
    username: Optional[str] = Query(default=None, description="Partial username search"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    _: Optional[User] = Depends(get_optional_user),  # optional auth — guests can search too
):
    return await user_service.get_all_users(session, username=username, skip=skip, limit=limit)


@user_router.get("/users/{user_id}", response_model=UserSafe)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.get_user(user_id, session)
    if not user or user.is_banned:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@user_router.get("/users/by-username/{username}", response_model=UserSafe)
async def get_user_by_username(
    username: str,
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.get_user_by_username(username, session)
    if not user or user.is_banned:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@user_router.post("/users/{user_id}/follow")
@limiter.limit(WRITE_LIMIT)
async def follow_user(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Follow a user. If their account is private a follow *request* is sent
    and must be accepted before the follow is active.
    """
    result = await user_service.follow_user(current_user.id, user_id, session)
    return result  


@user_router.delete("/users/{user_id}/follow", status_code=status.HTTP_200_OK)
@limiter.limit(WRITE_LIMIT)
async def unfollow_user(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await user_service.unfollow_user(current_user.id, user_id, session)
    return {"message": "Unfollowed successfully"}


@user_router.post("/follow-requests/{requester_id}/accept")
async def accept_follow_request(
    requester_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await user_service.accept_follow_request(current_user.id, requester_id, session)
    return {"message": "Follow request accepted"}


@user_router.delete("/follow-requests/{requester_id}/reject")
async def reject_follow_request(
    requester_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await user_service.reject_follow_request(current_user.id, requester_id, session)
    return {"message": "Follow request rejected"}


@user_router.delete("/users/{follower_id}/remove-follower")
async def remove_follower(
    follower_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Remove someone from your followers list (soft-remove without blocking)."""
    await user_service.remove_follower(current_user.id, follower_id, session)
    return {"message": "Follower removed"}


@user_router.get("/users/{user_id}/followers", response_model=List[UserPublic])
async def get_followers(
    user_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    target = await user_service.get_user(user_id, session)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.is_private and target.id != current_user.id:
        row = await session.exec(
            select(Follow).where(
                Follow.follower_id == current_user.id,
                Follow.followed_id == user_id,
                Follow.status == FollowStatusEnum.ACCEPTED,
            )
        )
        if not row.first():
            raise HTTPException(status_code=403, detail="This account is private")

    return await user_service.get_followers(user_id, session, skip=skip, limit=limit)


@user_router.get("/users/{user_id}/following", response_model=List[UserPublic])
async def get_following(
    user_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    target = await user_service.get_user(user_id, session)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.is_private and target.id != current_user.id:
        from ..db.models import Follow, FollowStatusEnum
        row = await session.exec(
            select(Follow).where(
                Follow.follower_id == current_user.id,
                Follow.followed_id == user_id,
                Follow.status == FollowStatusEnum.ACCEPTED,
            )
        )
        if not row.first():
            raise HTTPException(status_code=403, detail="This account is private")

    return await user_service.get_following(user_id, session, skip=skip, limit=limit)


@user_router.get("/users/me/follow-requests", response_model=List[UserPublic])
async def get_my_follow_requests(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Pending incoming follow requests (only relevant for private accounts)."""
    return await user_service.get_pending_follow_requests(current_user.id, session)


@user_router.post("/users/{user_id}/block", status_code=status.HTTP_200_OK)
@limiter.limit(WRITE_LIMIT)
async def block_user(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await user_service.block_user(current_user.id, user_id, session)
    return {"message": "User blocked"}


@user_router.delete("/users/{user_id}/block", status_code=status.HTTP_200_OK)
async def unblock_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await user_service.unblock_user(current_user.id, user_id, session)
    return {"message": "User unblocked"}


@user_router.get("/users/me/blocked", response_model=List[UserPublic])
async def get_blocked_users(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await user_service.get_blocked_users(current_user.id, session)


@user_router.delete(
    "/admin/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(admin_required)],
)
async def admin_delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await user_service.delete_user(user_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


@user_router.post(
    "/admin/users/{user_id}/ban",
    dependencies=[Depends(admin_required)],
)
async def admin_ban_user(
    user_id: int,
    reason: str = Query(..., min_length=5),
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.ban_user(user_id, reason, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User {user.username} has been banned"}


@user_router.post(
    "/admin/users/{user_id}/unban",
    dependencies=[Depends(admin_required)],
)
async def admin_unban_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.unban_user(user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User {user.username} has been unbanned"}