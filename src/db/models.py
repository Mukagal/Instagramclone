from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timedelta
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import ARRAY, Column, ForeignKey, Integer, UniqueConstraint, String, Text
import enum


class GenderEnum(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class MediaTypeEnum(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    REEL = "reel"
    CAROUSEL = "carousel"     

class NotificationTypeEnum(str, enum.Enum):
    LIKE = "like"
    COMMENT = "comment"
    COMMENT_LIKE = "comment_like"
    COMMENT_REPLY = "comment_reply"
    FOLLOW = "follow"
    FOLLOW_REQUEST = "follow_request"
    FOLLOW_ACCEPTED = "follow_accepted"
    MENTION = "mention"
    TAG = "tag"
    STORY_MENTION = "story_mention"
    STORY_REACTION = "story_reaction"
    REEL_LIKE = "reel_like"
    REEL_COMMENT = "reel_comment"
    LIVE_START = "live_start"


class ReportReasonEnum(str, enum.Enum):
    SPAM = "spam"
    NUDITY = "nudity"
    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    HARASSMENT = "harassment"
    FALSE_INFORMATION = "false_information"
    SCAM = "scam"
    OTHER = "other"


class ReportTargetTypeEnum(str, enum.Enum):
    POST = "post"
    COMMENT = "comment"
    STORY = "story"
    REEL = "reel"
    USER = "user"
    MESSAGE = "message"


class MessageTypeEnum(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    REEL_SHARE = "reel_share"
    POST_SHARE = "post_share"
    STORY_REPLY = "story_reply"
    VOICE = "voice"
    GIF = "gif"
    REACTION = "reaction"


class StoryReactionEnum(str, enum.Enum):
    HEART = "❤️"
    FIRE = "🔥"
    LAUGH = "😂"
    WOW = "😮"
    SAD = "😢"
    CLAP = "👏"
    THUMBSUP = "👍"
    HUNDRED = "💯"


class FollowStatusEnum(str, enum.Enum):
    PENDING = "pending"      
    ACCEPTED = "accepted"

class User(SQLModel, table=True):
    """Core account credentials and auth state."""
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)

    username: str = Field(index=True, nullable=False, unique=True, max_length=30)
    email: str = Field(index=True, nullable=False, unique=True)
    phone_number: Optional[str] = Field(default=None, unique=True)
    password_hash: str = Field(nullable=False)

    is_verified: bool = Field(default=False)
    is_banned: bool = Field(default=False)
    ban_reason: Optional[str] = Field(default=None)
    verification_token: Optional[str] = Field(default=None)
    reset_password_token: Optional[str] = Field(default=None)
    reset_token_expires_at: Optional[datetime] = Field(default=None)

    is_private: bool = Field(default=False) 
    is_business: bool = Field(default=False)
    is_creator: bool = Field(default=False)
    is_staff: bool = Field(default=False) 
    is_blue_verified: bool = Field(default=False)

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )
    last_seen_at: Optional[datetime] = Field(default=None)

    profile: Optional["UserProfile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"}
    )
    posts: List["Post"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    reels: List["Reel"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    stories: List["Story"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    following: List["Follow"] = Relationship(
        back_populates="follower",
        sa_relationship_kwargs={"foreign_keys": "[Follow.follower_id]", "cascade": "all, delete-orphan"}
    )
    followers: List["Follow"] = Relationship(
        back_populates="followed",
        sa_relationship_kwargs={"foreign_keys": "[Follow.followed_id]", "cascade": "all, delete-orphan"}
    )

    blocking: List["Block"] = Relationship(
        back_populates="blocker",
        sa_relationship_kwargs={"foreign_keys": "[Block.blocker_id]", "cascade": "all, delete-orphan"}
    )
    blocked_by: List["Block"] = Relationship(
        back_populates="blocked",
        sa_relationship_kwargs={"foreign_keys": "[Block.blocked_id]"}
    )

    close_friends: List["CloseFriend"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"foreign_keys": "[CloseFriend.owner_id]", "cascade": "all, delete-orphan"}
    )

    sent_messages: List["DirectMessage"] = Relationship(
        back_populates="sender",
        sa_relationship_kwargs={"foreign_keys": "[DirectMessage.sender_id]"}
    )

    notifications: List["Notification"] = Relationship(
        back_populates="recipient",
        sa_relationship_kwargs={"foreign_keys": "[Notification.recipient_id]", "cascade": "all, delete-orphan"}
    )

    saved_posts: List["SavedPost"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    highlighted_stories: List["StoryHighlight"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    hashtag_follows: List["HashtagFollow"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class UserProfile(SQLModel, table=True):
    """Extended profile info — one-to-one with User."""
    __tablename__ = "user_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)

    full_name: Optional[str] = Field(default=None, max_length=60)
    bio: Optional[str] = Field(default=None, max_length=150)
    website: Optional[str] = Field(default=None)
    gender: Optional[GenderEnum] = Field(default=None)

    avatar_path: Optional[str] = Field(default=None)

    category: Optional[str] = Field(default=None)
    contact_email: Optional[str] = Field(default=None)
    contact_phone: Optional[str] = Field(default=None)

    city: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)

    follower_count: int = Field(default=0)
    following_count: int = Field(default=0)
    post_count: int = Field(default=0)

    user: Optional[User] = Relationship(back_populates="profile")


class UserAvatar(SQLModel, table=True):
    """Compressed binary avatar thumbnail (one per user)."""
    __tablename__ = "user_avatars"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    image_data: bytes = Field(sa_column=Column(pg.BYTEA, nullable=False))
    original_size: int
    compressed_size: int
    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )


class Follow(SQLModel, table=True):
    """
    Follower → Followed relationship.
    status=PENDING when the followed account is private.
    """
    __tablename__ = "follows"

    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="unique_follow"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    follower_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    followed_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    status: FollowStatusEnum = Field(default=FollowStatusEnum.ACCEPTED)

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    follower: Optional[User] = Relationship(
        back_populates="following",
        sa_relationship_kwargs={"foreign_keys": "[Follow.follower_id]"}
    )
    followed: Optional[User] = Relationship(
        back_populates="followers",
        sa_relationship_kwargs={"foreign_keys": "[Follow.followed_id]"}
    )


class Block(SQLModel, table=True):
    """A blocks B — B cannot see A's content or send DMs."""
    __tablename__ = "blocks"

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="unique_block"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    blocker_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    blocked_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    blocker: Optional[User] = Relationship(
        back_populates="blocking",
        sa_relationship_kwargs={"foreign_keys": "[Block.blocker_id]"}
    )
    blocked: Optional[User] = Relationship(
        back_populates="blocked_by",
        sa_relationship_kwargs={"foreign_keys": "[Block.blocked_id]"}
    )


class CloseFriend(SQLModel, table=True):
    """Instagram 'Close Friends' list — used to restrict Story visibility."""
    __tablename__ = "close_friends"

    __table_args__ = (
        UniqueConstraint("owner_id", "friend_id", name="unique_close_friend"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    friend_id: int = Field(foreign_key="users.id")
    added_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    owner: Optional[User] = Relationship(
        back_populates="close_friends",
        sa_relationship_kwargs={"foreign_keys": "[CloseFriend.owner_id]"}
    )

class Hashtag(SQLModel, table=True):
    __tablename__ = "hashtags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, nullable=False)   
    post_count: int = Field(default=0)                          
    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    posts: List["PostHashtag"] = Relationship(back_populates="hashtag")
    reels: List["ReelHashtag"] = Relationship(back_populates="hashtag")
    followers: List["HashtagFollow"] = Relationship(back_populates="hashtag")


class HashtagFollow(SQLModel, table=True):
    """Users can follow hashtags to see tagged content in their feed."""
    __tablename__ = "hashtag_follows"

    __table_args__ = (
        UniqueConstraint("user_id", "hashtag_id", name="unique_hashtag_follow"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    hashtag_id: int = Field(foreign_key="hashtags.id")
    followed_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    user: Optional[User] = Relationship(back_populates="hashtag_follows")
    hashtag: Optional[Hashtag] = Relationship(back_populates="followers")



class Post(SQLModel, table=True):
    """
    A feed post. Can be a single image, video, or a carousel
    (multiple media items stored in PostMedia).
    """
    __tablename__ = "posts"

    id: Optional[int] = Field(default=None, primary_key=True)
    author_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )

    caption: Optional[str] = Field(default=None, max_length=2200)
    media_type: MediaTypeEnum = Field(default=MediaTypeEnum.IMAGE)

    location_name: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)

    is_archived: bool = Field(default=False)
    hide_like_count: bool = Field(default=False) 
    disable_comments: bool = Field(default=False)

    is_flagged: bool = Field(default=False)
    flag_reason: Optional[str] = Field(default=None)

    like_count: int = Field(default=0)
    comment_count: int = Field(default=0)
    share_count: int = Field(default=0)
    save_count: int = Field(default=0)

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )
    updated_at: Optional[datetime] = Field(default=None)

    author: Optional[User] = Relationship(back_populates="posts")

    media_items: List["PostMedia"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "PostMedia.position"}
    )
    likes: List["PostLike"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    comments: List["PostComment"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    hashtags: List["PostHashtag"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    user_tags: List["PostUserTag"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    saved_by: List["SavedPost"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    reports: List["Report"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"foreign_keys": "[Report.post_id]", "cascade": "all, delete-orphan"}
    )


class PostMedia(SQLModel, table=True):
    """
    One row per media file in a post.
    A single-image post has exactly one row; a carousel has ≥2.
    """
    __tablename__ = "post_media"

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(
        sa_column=Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    )
    position: int = Field(default=0)           
    media_type: MediaTypeEnum = Field(default=MediaTypeEnum.IMAGE)
    media_path: str                            
    thumbnail_path: Optional[str] = Field(default=None)
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    duration_seconds: Optional[float] = Field(default=None)   

    alt_text: Optional[str] = Field(default=None, max_length=100)

    post: Optional[Post] = Relationship(back_populates="media_items")


class PostLike(SQLModel, table=True):
    __tablename__ = "post_likes"

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="unique_post_like"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(
        sa_column=Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    liked_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    post: Optional[Post] = Relationship(back_populates="likes")


class PostHashtag(SQLModel, table=True):
    """Many-to-many: Post ↔ Hashtag."""
    __tablename__ = "post_hashtags"

    __table_args__ = (
        UniqueConstraint("post_id", "hashtag_id", name="unique_post_hashtag"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(
        sa_column=Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    )
    hashtag_id: int = Field(foreign_key="hashtags.id")

    post: Optional[Post] = Relationship(back_populates="hashtags")
    hashtag: Optional[Hashtag] = Relationship(back_populates="posts")


class PostUserTag(SQLModel, table=True):
    """People tagged in a post (collab tag or photo tag)."""
    __tablename__ = "post_user_tags"

    __table_args__ = (
        UniqueConstraint("post_id", "tagged_user_id", name="unique_post_user_tag"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(
        sa_column=Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    )
    tagged_user_id: int = Field(foreign_key="users.id")
    x_pct: Optional[float] = Field(default=None)
    y_pct: Optional[float] = Field(default=None)
    tagged_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    post: Optional[Post] = Relationship(back_populates="user_tags")


class SavedPost(SQLModel, table=True):
    """User bookmarks a post (saved to a collection or default saves)."""
    __tablename__ = "saved_posts"

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="unique_saved_post"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    post_id: int = Field(
        sa_column=Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    )
    collection_id: Optional[int] = Field(default=None, foreign_key="saved_collections.id")
    saved_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    user: Optional[User] = Relationship(back_populates="saved_posts")
    post: Optional[Post] = Relationship(back_populates="saved_by")
    collection: Optional["SavedCollection"] = Relationship(back_populates="saved_posts")


class SavedCollection(SQLModel, table=True):
    """Named collection for saved posts (like Instagram Collections)."""
    __tablename__ = "saved_collections"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    name: str = Field(max_length=60)
    cover_media_path: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    saved_posts: List[SavedPost] = Relationship(
        back_populates="collection",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class PostComment(SQLModel, table=True):
    """
    Comment on a Post.
    Top-level comments have parent_id=None.
    Replies have parent_id pointing to a top-level comment.
    (Instagram supports 1-level deep threading.)
    """
    __tablename__ = "post_comments"

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(
        sa_column=Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    )
    author_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    parent_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=True)
    )

    content: str = Field(sa_column=Column(Text, nullable=False), max_length=2200)

    like_count: int = Field(default=0)
    reply_count: int = Field(default=0)

    is_flagged: bool = Field(default=False)
    flag_reason: Optional[str] = Field(default=None)

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )
    updated_at: Optional[datetime] = Field(default=None)

    post: Optional[Post] = Relationship(back_populates="comments")

    replies: List["PostComment"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "foreign_keys": "[PostComment.parent_id]",
            "cascade": "all, delete-orphan"
        }
    )
    parent: Optional["PostComment"] = Relationship(
        back_populates="replies",
        sa_relationship_kwargs={"foreign_keys": "[PostComment.parent_id]", "remote_side": "PostComment.id"}
    )

    likes: List["CommentLike"] = Relationship(
        back_populates="comment",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    mentions: List["CommentMention"] = Relationship(
        back_populates="comment",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    reports: List["Report"] = Relationship(
        back_populates="comment",
        sa_relationship_kwargs={"foreign_keys": "[Report.comment_id]"}
    )


class CommentLike(SQLModel, table=True):
    __tablename__ = "comment_likes"

    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="unique_comment_like"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    comment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    liked_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    comment: Optional[PostComment] = Relationship(back_populates="likes")


class CommentMention(SQLModel, table=True):
    """@mentions parsed out of comment content."""
    __tablename__ = "comment_mentions"

    id: Optional[int] = Field(default=None, primary_key=True)
    comment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=False)
    )
    mentioned_user_id: int = Field(foreign_key="users.id")

    comment: Optional[PostComment] = Relationship(back_populates="mentions")

class Story(SQLModel, table=True):
    """
    24-hour story. Can be image or short video.
    Audience can be: everyone, followers, or close_friends_only.
    """
    __tablename__ = "stories"

    id: Optional[int] = Field(default=None, primary_key=True)
    author_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )

    media_path: str
    media_type: MediaTypeEnum = Field(default=MediaTypeEnum.IMAGE)
    thumbnail_path: Optional[str] = Field(default=None)
    duration_seconds: Optional[float] = Field(default=None)

    overlay_data: Optional[str] = Field(default=None)    # JSON

    caption: Optional[str] = Field(default=None, max_length=2200)

    location_name: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)

    close_friends_only: bool = Field(default=False)

    link_url: Optional[str] = Field(default=None)

    view_count: int = Field(default=0)

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )
    expires_at: datetime = Field(
        sa_column=Column(
            pg.TIMESTAMP,
            default=lambda: datetime.utcnow() + timedelta(hours=24)
        )
    )

    author: Optional[User] = Relationship(back_populates="stories")

    views: List["StoryView"] = Relationship(
        back_populates="story",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    reactions: List["StoryReaction"] = Relationship(
        back_populates="story",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    mentions: List["StoryMention"] = Relationship(
        back_populates="story",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    highlight_items: List["StoryHighlightItem"] = Relationship(
        back_populates="story"
    )
    poll: Optional["StoryPoll"] = Relationship(
        back_populates="story",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"}
    )
    question: Optional["StoryQuestion"] = Relationship(
        back_populates="story",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"}
    )
    reports: List["Report"] = Relationship(
        back_populates="story",
        sa_relationship_kwargs={"foreign_keys": "[Report.story_id]"}
    )


class StoryView(SQLModel, table=True):
    """Who viewed a story (visible to the story author only)."""
    __tablename__ = "story_views"

    __table_args__ = (
        UniqueConstraint("story_id", "viewer_id", name="unique_story_view"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(
        sa_column=Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    )
    viewer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    viewed_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    story: Optional[Story] = Relationship(back_populates="views")


class StoryReaction(SQLModel, table=True):
    """Emoji reaction sent on a story (appears as DM to author)."""
    __tablename__ = "story_reactions"

    __table_args__ = (
        UniqueConstraint("story_id", "reactor_id", name="unique_story_reaction"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(
        sa_column=Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    )
    reactor_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    reaction: StoryReactionEnum
    reacted_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    story: Optional[Story] = Relationship(back_populates="reactions")


class StoryMention(SQLModel, table=True):
    """@mention sticker in a story."""
    __tablename__ = "story_mentions"

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(
        sa_column=Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    )
    mentioned_user_id: int = Field(foreign_key="users.id")

    story: Optional[Story] = Relationship(back_populates="mentions")


class StoryPoll(SQLModel, table=True):
    """Poll sticker attached to a story."""
    __tablename__ = "story_polls"

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(
        sa_column=Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, unique=True)
    )
    question: str = Field(max_length=200)
    option_a: str = Field(max_length=100)
    option_b: str = Field(max_length=100)
    votes_a: int = Field(default=0)
    votes_b: int = Field(default=0)

    story: Optional[Story] = Relationship(back_populates="poll")
    votes: List["StoryPollVote"] = Relationship(
        back_populates="poll",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class StoryPollVote(SQLModel, table=True):
    __tablename__ = "story_poll_votes"

    __table_args__ = (
        UniqueConstraint("poll_id", "voter_id", name="unique_poll_vote"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    poll_id: int = Field(
        sa_column=Column(Integer, ForeignKey("story_polls.id", ondelete="CASCADE"), nullable=False)
    )
    voter_id: int = Field(foreign_key="users.id")
    choice: str = Field(max_length=1)   # 'a' or 'b'
    voted_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    poll: Optional[StoryPoll] = Relationship(back_populates="votes")


class StoryQuestion(SQLModel, table=True):
    """Question sticker attached to a story."""
    __tablename__ = "story_questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(
        sa_column=Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, unique=True)
    )
    prompt: str = Field(max_length=200)

    story: Optional[Story] = Relationship(back_populates="question")
    answers: List["StoryQuestionAnswer"] = Relationship(
        back_populates="question",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class StoryQuestionAnswer(SQLModel, table=True):
    __tablename__ = "story_question_answers"

    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int = Field(
        sa_column=Column(Integer, ForeignKey("story_questions.id", ondelete="CASCADE"), nullable=False)
    )
    responder_id: int = Field(foreign_key="users.id")
    answer_text: str = Field(max_length=150)
    answered_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    question: Optional[StoryQuestion] = Relationship(back_populates="answers")


class StoryHighlight(SQLModel, table=True):
    """Named highlight album on a user's profile (persists beyond 24h)."""
    __tablename__ = "story_highlights"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    title: str = Field(max_length=15)          # Instagram limit: 15 chars
    cover_path: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    user: Optional[User] = Relationship(back_populates="highlighted_stories")
    items: List["StoryHighlightItem"] = Relationship(
        back_populates="highlight",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class StoryHighlightItem(SQLModel, table=True):
    """Join table: stories added to a highlight."""
    __tablename__ = "story_highlight_items"

    __table_args__ = (
        UniqueConstraint("highlight_id", "story_id", name="unique_highlight_item"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    highlight_id: int = Field(
        sa_column=Column(Integer, ForeignKey("story_highlights.id", ondelete="CASCADE"), nullable=False)
    )
    story_id: int = Field(
        sa_column=Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    )
    position: int = Field(default=0)
    added_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    highlight: Optional[StoryHighlight] = Relationship(back_populates="items")
    story: Optional[Story] = Relationship(back_populates="highlight_items")


class Reel(SQLModel, table=True):
    """Short-form vertical video (Instagram Reels)."""
    __tablename__ = "reels"

    id: Optional[int] = Field(default=None, primary_key=True)
    author_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )

    video_path: str
    thumbnail_path: Optional[str] = Field(default=None)
    duration_seconds: float

    caption: Optional[str] = Field(default=None, max_length=2200)
    audio_name: Optional[str] = Field(default=None)  
    audio_path: Optional[str] = Field(default=None)   

    original_reel_id: Optional[int] = Field(default=None, foreign_key="reels.id")

    location_name: Optional[str] = Field(default=None)

    hide_like_count: bool = Field(default=False)
    disable_comments: bool = Field(default=False)
    is_flagged: bool = Field(default=False)

    like_count: int = Field(default=0)
    comment_count: int = Field(default=0)
    share_count: int = Field(default=0)
    view_count: int = Field(default=0)

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    author: Optional[User] = Relationship(back_populates="reels")

    likes: List["ReelLike"] = Relationship(
        back_populates="reel",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    comments: List["ReelComment"] = Relationship(
        back_populates="reel",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    hashtags: List["ReelHashtag"] = Relationship(
        back_populates="reel",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    user_tags: List["ReelUserTag"] = Relationship(
        back_populates="reel",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    views: List["ReelView"] = Relationship(
        back_populates="reel",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    reports: List["Report"] = Relationship(
        back_populates="reel",
        sa_relationship_kwargs={"foreign_keys": "[Report.reel_id]"}
    )


class ReelLike(SQLModel, table=True):
    __tablename__ = "reel_likes"

    __table_args__ = (
        UniqueConstraint("reel_id", "user_id", name="unique_reel_like"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    reel_id: int = Field(
        sa_column=Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    liked_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    reel: Optional[Reel] = Relationship(back_populates="likes")


class ReelComment(SQLModel, table=True):
    """
    Comment on a Reel.
    Threaded exactly like PostComment (1-level deep replies).
    """
    __tablename__ = "reel_comments"

    id: Optional[int] = Field(default=None, primary_key=True)
    reel_id: int = Field(
        sa_column=Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False)
    )
    author_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    parent_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("reel_comments.id", ondelete="CASCADE"), nullable=True)
    )

    content: str = Field(sa_column=Column(Text, nullable=False), max_length=2200)
    like_count: int = Field(default=0)
    reply_count: int = Field(default=0)
    is_flagged: bool = Field(default=False)

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    reel: Optional[Reel] = Relationship(back_populates="comments")

    replies: List["ReelComment"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "foreign_keys": "[ReelComment.parent_id]",
            "cascade": "all, delete-orphan"
        }
    )
    parent: Optional["ReelComment"] = Relationship(
        back_populates="replies",
        sa_relationship_kwargs={"foreign_keys": "[ReelComment.parent_id]", "remote_side": "ReelComment.id"}
    )
    likes: List["ReelCommentLike"] = Relationship(
        back_populates="comment",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class ReelCommentLike(SQLModel, table=True):
    __tablename__ = "reel_comment_likes"

    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="unique_reel_comment_like"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    comment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("reel_comments.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    liked_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    comment: Optional[ReelComment] = Relationship(back_populates="likes")


class ReelHashtag(SQLModel, table=True):
    __tablename__ = "reel_hashtags"

    __table_args__ = (
        UniqueConstraint("reel_id", "hashtag_id", name="unique_reel_hashtag"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    reel_id: int = Field(
        sa_column=Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False)
    )
    hashtag_id: int = Field(foreign_key="hashtags.id")

    reel: Optional[Reel] = Relationship(back_populates="hashtags")
    hashtag: Optional[Hashtag] = Relationship(back_populates="reels")


class ReelUserTag(SQLModel, table=True):
    __tablename__ = "reel_user_tags"

    __table_args__ = (
        UniqueConstraint("reel_id", "tagged_user_id", name="unique_reel_user_tag"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    reel_id: int = Field(
        sa_column=Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False)
    )
    tagged_user_id: int = Field(foreign_key="users.id")

    reel: Optional[Reel] = Relationship(back_populates="user_tags")


class ReelView(SQLModel, table=True):
    """Tracks who watched a reel (anonymous views counted separately via view_count)."""
    __tablename__ = "reel_views"

    __table_args__ = (
        UniqueConstraint("reel_id", "viewer_id", name="unique_reel_view"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    reel_id: int = Field(
        sa_column=Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False)
    )
    viewer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    watched_seconds: Optional[float] = Field(default=None)
    viewed_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    reel: Optional[Reel] = Relationship(back_populates="views")


class DirectThread(SQLModel, table=True):
    """
    A conversation thread. Supports both 1-to-1 and group DMs.
    For 1-to-1: exactly two ThreadMember rows. 
    For groups: name + cover image are set.
    """
    __tablename__ = "direct_threads"

    id: Optional[int] = Field(default=None, primary_key=True)

    is_group: bool = Field(default=False)
    group_name: Optional[str] = Field(default=None, max_length=50)
    group_cover_path: Optional[str] = Field(default=None)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )
    last_message_at: Optional[datetime] = Field(default=None)

    members: List["ThreadMember"] = Relationship(
        back_populates="thread",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    messages: List["DirectMessage"] = Relationship(
        back_populates="thread",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class ThreadMember(SQLModel, table=True):
    __tablename__ = "thread_members"

    __table_args__ = (
        UniqueConstraint("thread_id", "user_id", name="unique_thread_member"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(
        sa_column=Column(Integer, ForeignKey("direct_threads.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    is_admin: bool = Field(default=False)        # group admins
    last_read_at: Optional[datetime] = Field(default=None)
    joined_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )
    left_at: Optional[datetime] = Field(default=None)     # soft-leave for groups

    thread: Optional[DirectThread] = Relationship(back_populates="members")


class DirectMessage(SQLModel, table=True):
    __tablename__ = "direct_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(
        sa_column=Column(Integer, ForeignKey("direct_threads.id", ondelete="CASCADE"), nullable=False)
    )
    sender_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )

    message_type: MessageTypeEnum = Field(default=MessageTypeEnum.TEXT)
    content: Optional[str] = Field(default=None)            
    media_path: Optional[str] = Field(default=None)         

    shared_post_id: Optional[int] = Field(default=None, foreign_key="posts.id")
    shared_reel_id: Optional[int] = Field(default=None, foreign_key="reels.id")
    story_reply_id: Optional[int] = Field(default=None, foreign_key="stories.id")

    reply_to_message_id: Optional[int] = Field(default=None, foreign_key="direct_messages.id")

    is_disappearing: bool = Field(default=False)
    disappears_at: Optional[datetime] = Field(default=None)

    is_deleted: bool = Field(default=False)      # unsend

    sent_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    thread: Optional[DirectThread] = Relationship(back_populates="messages")
    sender: Optional[User] = Relationship(
        back_populates="sent_messages",
        sa_relationship_kwargs={"foreign_keys": "[DirectMessage.sender_id]"}
    )
    reactions: List["MessageReaction"] = Relationship(
        back_populates="message",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    read_receipts: List["MessageReadReceipt"] = Relationship(
        back_populates="message",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class MessageReaction(SQLModel, table=True):
    """Emoji reaction on a DM."""
    __tablename__ = "message_reactions"

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="unique_message_reaction"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: int = Field(
        sa_column=Column(Integer, ForeignKey("direct_messages.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    emoji: str = Field(max_length=10)
    reacted_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    message: Optional[DirectMessage] = Relationship(back_populates="reactions")


class MessageReadReceipt(SQLModel, table=True):
    """Tracks which members have read each message (for group DMs)."""
    __tablename__ = "message_read_receipts"

    __table_args__ = (
        UniqueConstraint("message_id", "reader_id", name="unique_read_receipt"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: int = Field(
        sa_column=Column(Integer, ForeignKey("direct_messages.id", ondelete="CASCADE"), nullable=False)
    )
    reader_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    read_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    message: Optional[DirectMessage] = Relationship(back_populates="read_receipts")


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    recipient_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    actor_id: Optional[int] = Field(default=None, foreign_key="users.id")   # who triggered it

    notification_type: NotificationTypeEnum
    is_read: bool = Field(default=False)

    post_id: Optional[int] = Field(default=None, foreign_key="posts.id")
    reel_id: Optional[int] = Field(default=None, foreign_key="reels.id")
    story_id: Optional[int] = Field(default=None, foreign_key="stories.id")
    comment_id: Optional[int] = Field(default=None, foreign_key="post_comments.id")
    follow_id: Optional[int] = Field(default=None, foreign_key="follows.id")

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    recipient: Optional[User] = Relationship(
        back_populates="notifications",
        sa_relationship_kwargs={"foreign_keys": "[Notification.recipient_id]"}
    )


class Report(SQLModel, table=True):
    """User reports content or another account."""
    __tablename__ = "reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    reporter_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )

    target_type: ReportTargetTypeEnum
    reason: ReportReasonEnum
    details: Optional[str] = Field(default=None, max_length=500)

    is_resolved: bool = Field(default=False)
    resolved_at: Optional[datetime] = Field(default=None)
    moderator_note: Optional[str] = Field(default=None)

    post_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    )
    comment_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("post_comments.id", ondelete="SET NULL"), nullable=True)
    )
    story_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("stories.id", ondelete="SET NULL"), nullable=True)
    )
    reel_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("reels.id", ondelete="SET NULL"), nullable=True)
    )
    reported_user_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    )

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    post: Optional[Post] = Relationship(
        back_populates="reports",
        sa_relationship_kwargs={"foreign_keys": "[Report.post_id]"}
    )
    comment: Optional[PostComment] = Relationship(
        back_populates="reports",
        sa_relationship_kwargs={"foreign_keys": "[Report.comment_id]"}
    )
    story: Optional[Story] = Relationship(
        back_populates="reports",
        sa_relationship_kwargs={"foreign_keys": "[Report.story_id]"}
    )
    reel: Optional[Reel] = Relationship(
        back_populates="reports",
        sa_relationship_kwargs={"foreign_keys": "[Report.reel_id]"}
    )


class SearchHistory(SQLModel, table=True):
    """Tracks recent searches per user (shown in Explore search bar)."""
    __tablename__ = "search_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    query: Optional[str] = Field(default=None)               # free-text search
    searched_user_id: Optional[int] = Field(default=None, foreign_key="users.id")   # profile tapped
    searched_hashtag_id: Optional[int] = Field(default=None, foreign_key="hashtags.id")
    searched_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )


class LiveStream(SQLModel, table=True):
    """Instagram Live session."""
    __tablename__ = "live_streams"

    id: Optional[int] = Field(default=None, primary_key=True)
    host_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    title: Optional[str] = Field(default=None, max_length=100)
    stream_key: str = Field(unique=True)       # RTMP / HLS key
    thumbnail_path: Optional[str] = Field(default=None)

    is_active: bool = Field(default=True)
    viewer_count: int = Field(default=0)
    peak_viewer_count: int = Field(default=0)

    started_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )
    ended_at: Optional[datetime] = Field(default=None)

    comments: List["LiveComment"] = Relationship(
        back_populates="stream",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    reactions: List["LiveReaction"] = Relationship(
        back_populates="stream",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class LiveComment(SQLModel, table=True):
    __tablename__ = "live_comments"

    id: Optional[int] = Field(default=None, primary_key=True)
    stream_id: int = Field(
        sa_column=Column(Integer, ForeignKey("live_streams.id", ondelete="CASCADE"), nullable=False)
    )
    author_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    content: str = Field(max_length=500)
    sent_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    stream: Optional[LiveStream] = Relationship(back_populates="comments")


class LiveReaction(SQLModel, table=True):
    __tablename__ = "live_reactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    stream_id: int = Field(
        sa_column=Column(Integer, ForeignKey("live_streams.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    emoji: str = Field(max_length=10)
    reacted_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )

    stream: Optional[LiveStream] = Relationship(back_populates="reactions")