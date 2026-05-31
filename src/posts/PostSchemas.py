from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum
from ..db.models import MediaTypeEnum



class SortBy(str, Enum):
    latest = "latest"
    likes = "likes"
    comments = "comments"


class PostCreate(BaseModel):
    caption: Optional[str] = Field(default=None, max_length=2200)
    location_name: Optional[str] = None
    hide_like_count: bool = False
    disable_comments: bool = False


class PostUpdate(BaseModel):
    caption: Optional[str] = Field(default=None, max_length=2200)
    location_name: Optional[str] = None
    hide_like_count: Optional[bool] = None
    disable_comments: Optional[bool] = None


class PostMediaOut(BaseModel):
    id: int
    position: int
    media_type: MediaTypeEnum
    media_path: str
    thumbnail_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    alt_text: Optional[str] = None

    class Config:
        from_attributes = True


class AuthorOut(BaseModel):
    id: int
    username: str
    avatar_path: Optional[str] = None   
    is_blue_verified: bool = False

    class Config:
        from_attributes = True


class PostResponse(BaseModel):
    id: int
    author_id: int
    author: Optional[AuthorOut] = None
    caption: Optional[str] = None
    media_type: MediaTypeEnum
    location_name: Optional[str] = None
    hide_like_count: bool = False
    disable_comments: bool = False
    like_count: int = 0
    comment_count: int = 0
    save_count: int = 0
    media_items: List[PostMediaOut] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    content: str = Field(max_length=2200)
    parent_id: Optional[int] = None    


class CommentUpdate(BaseModel):
    content: str = Field(max_length=2200)


class CommentResponse(BaseModel):
    id: int
    post_id: int
    author_id: int
    author_username: Optional[str] = None
    author_avatar: Optional[str] = None
    parent_id: Optional[int] = None
    content: str
    like_count: int = 0
    reply_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    replies: List["CommentResponse"] = []

    class Config:
        from_attributes = True

CommentResponse.model_rebuild()


class CommentLikeResponse(BaseModel):
    comment_id: int
    likes: int



class LikeResponse(BaseModel):
    post_id: int
    likes: int


class LikerOut(BaseModel):
    user_id: int
    username: str
    avatar_path: Optional[str] = None
    liked_at: datetime

    class Config:
        from_attributes = True



class SaveResponse(BaseModel):
    post_id: int
    saved: bool


class CollectionCreate(BaseModel):
    name: str = Field(max_length=60)


class CollectionOut(BaseModel):
    id: int
    name: str
    cover_media_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True



class PostInteractionSummary(BaseModel):
    post_id: int
    caption_preview: Optional[str] = None
    like_count: int
    comment_count: int
    save_count: int