from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
from ..db.models import MediaTypeEnum, StoryReactionEnum



class PollCreate(BaseModel):
    question: str = Field(max_length=200)
    option_a: str = Field(max_length=100)
    option_b: str = Field(max_length=100)


class QuestionCreate(BaseModel):
    prompt: str = Field(max_length=200)


class StoryCreate(BaseModel):
    caption: Optional[str] = Field(default=None, max_length=2200)
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    close_friends_only: bool = False
    link_url: Optional[str] = None
    poll: Optional[PollCreate] = None
    question: Optional[QuestionCreate] = None
    mention_user_ids: Optional[List[int]] = None

    @field_validator("link_url")
    @classmethod
    def validate_link(cls, v: Optional[str]) -> Optional[str]:
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("link_url must start with http:// or https://")
        return v


class PollOut(BaseModel):
    id: int
    question: str
    option_a: str
    option_b: str
    votes_a: int = 0
    votes_b: int = 0
    my_vote: Optional[str] = None

    class Config:
        from_attributes = True


class PollVoteCreate(BaseModel):
    choice: str = Field(pattern="^[ab]$") 


class QuestionOut(BaseModel):
    id: int
    prompt: str

    class Config:
        from_attributes = True


class QuestionAnswerCreate(BaseModel):
    answer_text: str = Field(max_length=150)


class QuestionAnswerOut(BaseModel):
    id: int
    responder_id: int
    responder_username: str
    responder_avatar: Optional[str] = None
    answer_text: str
    answered_at: datetime

    class Config:
        from_attributes = True

class StoryAuthorOut(BaseModel):
    id: int
    username: str
    avatar_path: Optional[str] = None
    is_blue_verified: bool = False

    class Config:
        from_attributes = True

class StoryOut(BaseModel):
    id: int
    author_id: int
    author: Optional[StoryAuthorOut] = None
    media_path: str
    media_type: MediaTypeEnum
    thumbnail_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    caption: Optional[str] = None
    location_name: Optional[str] = None
    close_friends_only: bool = False
    link_url: Optional[str] = None
    view_count: int = 0
    created_at: datetime
    expires_at: datetime
    has_viewed: bool = False        
    my_reaction: Optional[StoryReactionEnum] = None
    poll: Optional[PollOut] = None
    question: Optional[QuestionOut] = None

    class Config:
        from_attributes = True

class StoryTrayItem(BaseModel):
    """
    One row in the stories tray at the top of the feed.
    Represents one user's active stories.
    """
    user_id: int
    username: str
    avatar_path: Optional[str] = None
    is_blue_verified: bool = False
    has_unseen: bool = True         
    story_count: int = 1
    latest_story_at: datetime         

    class Config:
        from_attributes = True



class StoryViewerOut(BaseModel):
    user_id: int
    username: str
    avatar_path: Optional[str] = None
    reaction: Optional[StoryReactionEnum] = None
    viewed_at: datetime

    class Config:
        from_attributes = True


class StoryReactionCreate(BaseModel):
    reaction: StoryReactionEnum


class StoryReactionOut(BaseModel):
    story_id: int
    reactor_id: int
    reactor_username: str
    reactor_avatar: Optional[str] = None
    reaction: StoryReactionEnum
    reacted_at: datetime

    class Config:
        from_attributes = True


class HighlightCreate(BaseModel):
    title: str = Field(max_length=15)     
    story_ids: Optional[List[int]] = None


class HighlightUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=15)


class HighlightOut(BaseModel):
    id: int
    user_id: int
    title: str
    cover_path: Optional[str] = None
    story_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class HighlightDetailOut(HighlightOut):
    stories: List[StoryOut] = []