from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from ..db.models import NotificationTypeEnum


class NotificationActorOut(BaseModel):
    id: int
    username: str
    avatar_path: Optional[str] = None
    is_blue_verified: bool = False


class NotificationOut(BaseModel):
    id: int
    recipient_id: int
    actor_id: Optional[int] = None
    actor: Optional[NotificationActorOut] = None
    notification_type: NotificationTypeEnum
    is_read: bool
    post_id: Optional[int] = None
    reel_id: Optional[int] = None
    story_id: Optional[int] = None
    comment_id: Optional[int] = None
    follow_id: Optional[int] = None
    created_at: datetime


class UnreadCountOut(BaseModel):
    count: int
