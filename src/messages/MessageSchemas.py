from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from ..db.models import MessageTypeEnum

class ThreadCreate(BaseModel):
    """Start a 1-to-1 DM thread with another user."""
    target_user_id: int


class GroupThreadCreate(BaseModel):
    """Create a group DM thread."""
    name: str = Field(max_length=50)
    member_ids: List[int] = Field(min_length=1)


class GroupThreadUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)


class MemberOut(BaseModel):
    user_id: int
    username: str
    avatar_path: Optional[str] = None
    is_admin: bool = False
    joined_at: datetime

    class Config:
        from_attributes = True


class ThreadOut(BaseModel):
    id: int
    is_group: bool = False
    group_name: Optional[str] = None
    group_cover_path: Optional[str] = None
    created_at: datetime
    last_message_at: Optional[datetime] = None
    members: List[MemberOut] = []
    last_message_preview: Optional[str] = None
    unread_count: int = 0

    class Config:
        from_attributes = True



class MessageSend(BaseModel):
    content: Optional[str] = Field(default=None, max_length=2000)
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    shared_post_id: Optional[int] = None
    shared_reel_id: Optional[int] = None
    story_reply_id: Optional[int] = None
    reply_to_message_id: Optional[int] = None
    is_disappearing: bool = False


class MessageReactionCreate(BaseModel):
    emoji: str = Field(max_length=10)


class ReactionOut(BaseModel):
    user_id: int
    username: str
    emoji: str
    reacted_at: datetime

    class Config:
        from_attributes = True


class ReadReceiptOut(BaseModel):
    reader_id: int
    username: str
    read_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    thread_id: int
    sender_id: int
    sender_username: str
    sender_avatar: Optional[str] = None
    message_type: MessageTypeEnum
    content: Optional[str] = None
    media_path: Optional[str] = None
    shared_post_id: Optional[int] = None
    shared_reel_id: Optional[int] = None
    story_reply_id: Optional[int] = None
    reply_to_message_id: Optional[int] = None
    is_disappearing: bool = False
    is_deleted: bool = False
    sent_at: datetime
    reactions: List[ReactionOut] = []
    read_receipts: List[ReadReceiptOut] = []

    class Config:
        from_attributes = True