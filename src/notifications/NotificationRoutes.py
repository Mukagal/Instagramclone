from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db.main import get_session
from ..db.models import User
from ..users.dependencies import get_current_user
from .NotificationSchemas import NotificationOut, UnreadCountOut
from .NotificationService import notification_service

notification_router = APIRouter()


@notification_router.get("/notifications", response_model=List[NotificationOut])
async def get_notifications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.get_notifications(
        current_user.id, session, skip=skip, limit=limit
    )


@notification_router.get(
    "/notifications/unread-count", response_model=UnreadCountOut
)
async def get_unread_count(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "count": await notification_service.get_unread_count(
            current_user.id, session
        )
    }


@notification_router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.mark_read(
        notification_id, current_user.id, session
    )


@notification_router.post("/notifications/read-all")
async def mark_all_notifications_read(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.mark_all_read(current_user.id, session)


@notification_router.delete(
    "/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_notification(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await notification_service.delete_notification(
        notification_id, current_user.id, session
    )
