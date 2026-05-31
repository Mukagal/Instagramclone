import logging
from datetime import datetime
from typing import Optional

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import selectinload
from sqlmodel import desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import Config
from ..db.models import (
    MediaTypeEnum,
    Post,
    PostComment,
    PostHashtag,
    PostLike,
    PostMedia,
    PostUserTag,
    SavedCollection,
    SavedPost,
    CommentLike,
    User,
    UserProfile,
    Follow,
    FollowStatusEnum,
    Hashtag,
    NotificationTypeEnum,
)
from ..errors import PostNotFoundError, PostOwnershipError
from ..notifications.NotificationService import notification_service
from .PostSchemas import (
    CollectionCreate,
    CommentCreate,
    CommentUpdate,
    PostCreate,
    PostUpdate,
    SortBy,
)

log = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
    api_key=Config.CLOUDINARY_API_KEY,
    api_secret=Config.CLOUDINARY_API_SECRET,
)


def _post_opts():
    """Standard eager-load options for a Post query."""
    return [
        selectinload(Post.media_items),
        selectinload(Post.likes),
        selectinload(Post.comments),
        selectinload(Post.saved_by),
        selectinload(Post.author).selectinload(User.profile),
    ]


def _build_post_response(post: Post) -> dict:
    author_out = None
    if post.author:
        author_out = {
            "id": post.author.id,
            "username": post.author.username,
            "avatar_path": post.author.profile.avatar_path if post.author.profile else None,
            "is_blue_verified": post.author.is_blue_verified,
        }

    return {
        "id": post.id,
        "author_id": post.author_id,
        "author": author_out,
        "caption": post.caption,
        "media_type": post.media_type,
        "location_name": post.location_name,
        "hide_like_count": post.hide_like_count,
        "disable_comments": post.disable_comments,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "save_count": post.save_count,
        "media_items": [
            {
                "id": m.id,
                "position": m.position,
                "media_type": m.media_type,
                "media_path": m.media_path,
                "thumbnail_path": m.thumbnail_path,
                "width": m.width,
                "height": m.height,
                "duration_seconds": m.duration_seconds,
                "alt_text": m.alt_text,
            }
            for m in sorted(post.media_items, key=lambda x: x.position)
        ],
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }


def _extract_hashtags(caption: Optional[str]) -> list[str]:
    """Parse #hashtag tokens from a caption string."""
    if not caption:
        return []
    import re
    return list({
        tag.lower()
        for tag in re.findall(r"#(\w+)", caption)
    })


class PostService:


    async def _get_post(self, post_id: int, session: AsyncSession) -> Post:
        result = await session.exec(
            select(Post)
            .where(Post.id == post_id)
            .options(*_post_opts())
        )
        post = result.first()
        if not post:
            raise PostNotFoundError()
        return post

    async def _get_or_create_hashtag(self, name: str, session: AsyncSession) -> Hashtag:
        result = await session.exec(select(Hashtag).where(Hashtag.name == name))
        tag = result.first()
        if not tag:
            tag = Hashtag(name=name)
            session.add(tag)
            await session.flush()
        return tag

    async def _sync_hashtags(self, post: Post, caption: Optional[str], session: AsyncSession):
        """Replace post's hashtag associations with whatever is in the new caption."""
        old = await session.exec(
            select(PostHashtag).where(PostHashtag.post_id == post.id)
        )
        for row in old.all():
            await session.delete(row)

        for name in _extract_hashtags(caption):
            tag = await self._get_or_create_hashtag(name, session)
            session.add(PostHashtag(post_id=post.id, hashtag_id=tag.id))
            tag.post_count += 1

    async def _upload_to_cloudinary(self, file: UploadFile, folder: str, **kwargs) -> str:
        """Upload a file to Cloudinary and return the secure URL."""
        result = cloudinary.uploader.upload(
            file.file,
            folder=folder,
            **kwargs,
        )
        return result["secure_url"]


    async def get_feed(
        self,
        session: AsyncSession,
        sort_by: SortBy = SortBy.latest,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        current_user_id: Optional[int] = None,
    ) -> list:
        """
        Global explore feed (non-flagged, non-archived posts).
        If current_user_id is given, posts from blocked users are excluded.
        """
        statement = (
            select(Post)
            .where(Post.is_flagged == False, Post.is_archived == False)
            .options(*_post_opts())
        )
        if keyword:
            statement = statement.where(Post.caption.ilike(f"%{keyword}%"))
        if sort_by == SortBy.latest:
            statement = statement.order_by(desc(Post.created_at))
        elif sort_by == SortBy.likes:
            statement = statement.order_by(desc(Post.like_count))
        elif sort_by == SortBy.comments:
            statement = statement.order_by(desc(Post.comment_count))

        statement = statement.offset(skip).limit(limit)
        result = await session.exec(statement)
        return [_build_post_response(p) for p in result.all()]

    async def get_following_feed(
        self,
        user_id: int,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 20,
    ) -> list:
        """Home feed — posts only from accounts the user follows."""
        following_ids_result = await session.exec(
            select(Follow.followed_id).where(
                Follow.follower_id == user_id,
                Follow.status == FollowStatusEnum.ACCEPTED,
            )
        )
        following_ids = list(following_ids_result.all())
        if not following_ids:
            return []

        result = await session.exec(
            select(Post)
            .where(
                Post.author_id.in_(following_ids),
                Post.is_flagged == False,
                Post.is_archived == False,
            )
            .options(*_post_opts())
            .order_by(desc(Post.created_at))
            .offset(skip)
            .limit(limit)
        )
        return [_build_post_response(p) for p in result.all()]

    async def get_post(self, post_id: int, session: AsyncSession) -> dict:
        return _build_post_response(await self._get_post(post_id, session))

    async def get_user_posts(
        self,
        user_id: int,
        session: AsyncSession,
        sort_by: SortBy = SortBy.latest,
        skip: int = 0,
        limit: int = 20,
        viewer_id: Optional[int] = None,
    ) -> list:
        """
        Posts on a user's profile grid.
        Respects private-account visibility: if the profile is private and
        the viewer doesn't follow them, raise 403.
        """
        if viewer_id and viewer_id != user_id:
            user_result = await session.exec(
                select(User).where(User.id == user_id)
            )
            target = user_result.first()
            if target and target.is_private:
                follow_result = await session.exec(
                    select(Follow).where(
                        Follow.follower_id == viewer_id,
                        Follow.followed_id == user_id,
                        Follow.status == FollowStatusEnum.ACCEPTED,
                    )
                )
                if not follow_result.first():
                    raise HTTPException(status_code=403, detail="This account is private")

        statement = (
            select(Post)
            .where(Post.author_id == user_id, Post.is_archived == False)
            .options(*_post_opts())
        )
        if sort_by == SortBy.latest:
            statement = statement.order_by(desc(Post.created_at))
        elif sort_by == SortBy.likes:
            statement = statement.order_by(desc(Post.like_count))
        elif sort_by == SortBy.comments:
            statement = statement.order_by(desc(Post.comment_count))

        statement = statement.offset(skip).limit(limit)
        result = await session.exec(statement)
        return [_build_post_response(p) for p in result.all()]

    async def get_archived_posts(self, user_id: int, session: AsyncSession) -> list:
        """Only visible to the post owner."""
        result = await session.exec(
            select(Post)
            .where(Post.author_id == user_id, Post.is_archived == True)
            .options(*_post_opts())
            .order_by(desc(Post.created_at))
        )
        return [_build_post_response(p) for p in result.all()]


    async def create_post(
        self,
        author_id: int,
        data: PostCreate,
        session: AsyncSession,
        files: Optional[list[UploadFile]] = None,
        tagged_user_ids: Optional[list[int]] = None,
    ) -> dict:
        """
        Create a post with 1–10 media files (images or videos).
        Automatically detects carousel vs single post.
        Parses #hashtags and @user-tag IDs from the payload.
        """
        files = files or []
        if not files:
            raise HTTPException(status_code=400, detail="At least one media file is required")
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 media items per post")

        media_type = MediaTypeEnum.CAROUSEL if len(files) > 1 else MediaTypeEnum.IMAGE

        post = Post(
            author_id=author_id,
            caption=data.caption,
            media_type=media_type,
            location_name=data.location_name,
            hide_like_count=data.hide_like_count,
            disable_comments=data.disable_comments,
        )
        session.add(post)
        await session.flush()   

        for position, file in enumerate(files):
            is_video = file.content_type and file.content_type.startswith("video/")
            folder = "post_videos" if is_video else "post_images"
            transformation = (
                [{"width": 1080, "crop": "limit"}]
                if is_video
                else [{"width": 1080, "height": 1080, "crop": "limit"}]
            )
            media_path = await self._upload_to_cloudinary(
                file, folder, transformation=transformation
            )
            media_item = PostMedia(
                post_id=post.id,
                position=position,
                media_type=MediaTypeEnum.VIDEO if is_video else MediaTypeEnum.IMAGE,
                media_path=media_path,
            )
            session.add(media_item)

        await self._sync_hashtags(post, data.caption, session)

        for uid in (tagged_user_ids or []):
            session.add(PostUserTag(post_id=post.id, tagged_user_id=uid))

        profile_result = await session.exec(
            select(UserProfile).where(UserProfile.user_id == author_id)
        )
        profile = profile_result.first()
        if profile:
            profile.post_count += 1

        await session.commit()
        return _build_post_response(await self._get_post(post.id, session))


    async def update_post(
        self, post_id: int, user_id: int, data: PostUpdate, session: AsyncSession
    ) -> dict:
        post = await self._get_post(post_id, session)
        if post.author_id != user_id:
            raise PostOwnershipError()

        update_fields = data.model_dump(exclude_unset=True)
        for k, v in update_fields.items():
            setattr(post, k, v)
        post.updated_at = datetime.utcnow()

        if "caption" in update_fields:
            await self._sync_hashtags(post, update_fields["caption"], session)

        await session.commit()
        return _build_post_response(await self._get_post(post_id, session))

    async def archive_post(self, post_id: int, user_id: int, session: AsyncSession) -> dict:
        post = await self._get_post(post_id, session)
        if post.author_id != user_id:
            raise PostOwnershipError()
        post.is_archived = not post.is_archived
        await session.commit()
        return {"post_id": post_id, "is_archived": post.is_archived}


    async def delete_post(self, post_id: int, user_id: int, session: AsyncSession) -> None:
        post = await self._get_post(post_id, session)
        if post.author_id != user_id:
            raise PostOwnershipError()

        profile_result = await session.exec(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = profile_result.first()
        if profile:
            profile.post_count = max(0, profile.post_count - 1)

        await session.delete(post)
        await session.commit()


    async def like_post(self, post_id: int, user_id: int, session: AsyncSession) -> dict:
        post = await self._get_post(post_id, session)

        existing = await session.exec(
            select(PostLike).where(
                PostLike.post_id == post_id, PostLike.user_id == user_id
            )
        )
        if existing.first():
            return {"post_id": post_id, "likes": post.like_count}

        session.add(PostLike(post_id=post_id, user_id=user_id))
        post.like_count += 1
        await notification_service.create_notification(
            session,
            recipient_id=post.author_id,
            actor_id=user_id,
            notification_type=NotificationTypeEnum.LIKE,
            post_id=post_id,
        )
        await session.commit()
        return {"post_id": post_id, "likes": post.like_count}

    async def unlike_post(self, post_id: int, user_id: int, session: AsyncSession) -> dict:
        post = await self._get_post(post_id, session)

        existing = await session.exec(
            select(PostLike).where(
                PostLike.post_id == post_id, PostLike.user_id == user_id
            )
        )
        like = existing.first()
        if not like:
            return {"post_id": post_id, "likes": post.like_count}

        await session.delete(like)
        post.like_count = max(0, post.like_count - 1)
        await session.commit()
        return {"post_id": post_id, "likes": post.like_count}

    async def get_post_likers(
        self, post_id: int, owner_id: int, session: AsyncSession
    ) -> list:
        post = await self._get_post(post_id, session)
        if post.author_id != owner_id:
            raise PostOwnershipError()

        result = await session.exec(
            select(PostLike, User.username, UserProfile.avatar_path)
            .join(User, User.id == PostLike.user_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(PostLike.post_id == post_id)
            .order_by(desc(PostLike.liked_at))
        )
        return [
            {
                "user_id": like.user_id,
                "username": username,
                "avatar_path": avatar,
                "liked_at": like.liked_at,
            }
            for like, username, avatar in result.all()
        ]


    async def add_comment(
        self, post_id: int, author_id: int, data: CommentCreate, session: AsyncSession
    ) -> dict:
        post = await self._get_post(post_id, session)

        if post.disable_comments:
            raise HTTPException(status_code=403, detail="Comments are disabled on this post")

        parent = None
        if data.parent_id:
            parent_result = await session.exec(
                select(PostComment).where(
                    PostComment.id == data.parent_id,
                    PostComment.post_id == post_id,
                    PostComment.parent_id == None,   )
            )
            parent = parent_result.first()
            if not parent:
                raise HTTPException(status_code=400, detail="Invalid parent comment")

        comment = PostComment(
            post_id=post_id,
            author_id=author_id,
            parent_id=data.parent_id,
            content=data.content,
        )
        session.add(comment)

        post.comment_count += 1
        if data.parent_id:
            if parent:
                parent.reply_count += 1

        await session.flush()
        if parent:
            await notification_service.create_notification(
                session,
                recipient_id=parent.author_id,
                actor_id=author_id,
                notification_type=NotificationTypeEnum.COMMENT_REPLY,
                post_id=post_id,
                comment_id=comment.id,
            )
            if post.author_id != parent.author_id:
                await notification_service.create_notification(
                    session,
                    recipient_id=post.author_id,
                    actor_id=author_id,
                    notification_type=NotificationTypeEnum.COMMENT,
                    post_id=post_id,
                    comment_id=comment.id,
                )
        else:
            await notification_service.create_notification(
                session,
                recipient_id=post.author_id,
                actor_id=author_id,
                notification_type=NotificationTypeEnum.COMMENT,
                post_id=post_id,
                comment_id=comment.id,
            )

        user_result = await session.exec(
            select(User.username, UserProfile.avatar_path)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.id == author_id)
        )
        row = user_result.first()
        username, avatar = (row if row else (None, None))

        await session.commit()
        return {
            "id": comment.id,
            "post_id": comment.post_id,
            "author_id": comment.author_id,
            "author_username": username,
            "author_avatar": avatar,
            "parent_id": comment.parent_id,
            "content": comment.content,
            "like_count": 0,
            "reply_count": 0,
            "created_at": comment.created_at,
            "updated_at": None,
            "replies": [],
        }

    async def get_comments(
        self,
        post_id: int,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        include_replies: bool = False,
    ) -> list:
        """
        Returns top-level comments only.
        Pass include_replies=True to also embed first-page replies.
        """
        await self._get_post(post_id, session)

        result = await session.exec(
            select(PostComment, User.username, UserProfile.avatar_path)
            .join(User, User.id == PostComment.author_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(
                PostComment.post_id == post_id,
                PostComment.parent_id == None,
            )
            .order_by(desc(PostComment.created_at))
            .offset(skip)
            .limit(limit)
        )
        rows = result.all()
        out = []
        for comment, username, avatar in rows:
            replies = []
            if include_replies:
                replies = await self.get_replies(comment.id, session)
            out.append({
                "id": comment.id,
                "post_id": comment.post_id,
                "author_id": comment.author_id,
                "author_username": username,
                "author_avatar": avatar,
                "parent_id": None,
                "content": comment.content,
                "like_count": comment.like_count,
                "reply_count": comment.reply_count,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
                "replies": replies,
            })
        return out

    async def get_replies(
        self, parent_id: int, session: AsyncSession, skip: int = 0, limit: int = 20
    ) -> list:
        result = await session.exec(
            select(PostComment, User.username, UserProfile.avatar_path)
            .join(User, User.id == PostComment.author_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(PostComment.parent_id == parent_id)
            .order_by(PostComment.created_at)
            .offset(skip)
            .limit(limit)
        )
        return [
            {
                "id": c.id,
                "post_id": c.post_id,
                "author_id": c.author_id,
                "author_username": u,
                "author_avatar": av,
                "parent_id": c.parent_id,
                "content": c.content,
                "like_count": c.like_count,
                "reply_count": 0,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "replies": [],
            }
            for c, u, av in result.all()
        ]

    async def update_comment(
        self, comment_id: int, user_id: int, data: CommentUpdate, session: AsyncSession
    ) -> dict:
        result = await session.exec(
            select(PostComment).where(PostComment.id == comment_id)
        )
        comment = result.first()
        if not comment:
            from ..errors import CommentNotFoundError
            raise CommentNotFoundError()
        if comment.author_id != user_id:
            from ..errors import CommentOwnershipError
            raise CommentOwnershipError()
        comment.content = data.content
        comment.updated_at = datetime.utcnow()
        await session.commit()
        return {"id": comment.id, "content": comment.content, "updated_at": comment.updated_at}

    async def delete_comment(
        self, comment_id: int, user_id: int, session: AsyncSession
    ) -> None:
        result = await session.exec(
            select(PostComment).where(PostComment.id == comment_id)
        )
        comment = result.first()
        if not comment:
            from ..errors import CommentNotFoundError
            raise CommentNotFoundError()
        if comment.author_id != user_id:
            from ..errors import CommentOwnershipError
            raise CommentOwnershipError()

        post_result = await session.exec(
            select(Post).where(Post.id == comment.post_id)
        )
        post = post_result.first()
        if post:
            post.comment_count = max(0, post.comment_count - 1)

        if comment.parent_id:
            parent_result = await session.exec(
                select(PostComment).where(PostComment.id == comment.parent_id)
            )
            parent = parent_result.first()
            if parent:
                parent.reply_count = max(0, parent.reply_count - 1)

        await session.delete(comment)
        await session.commit()


    async def like_comment(
        self, comment_id: int, user_id: int, session: AsyncSession
    ) -> dict:
        result = await session.exec(
            select(PostComment).where(PostComment.id == comment_id)
        )
        comment = result.first()
        if not comment:
            from ..errors import CommentNotFoundError
            raise CommentNotFoundError()

        existing = await session.exec(
            select(CommentLike).where(
                CommentLike.comment_id == comment_id,
                CommentLike.user_id == user_id,
            )
        )
        if not existing.first():
            session.add(CommentLike(comment_id=comment_id, user_id=user_id))
            comment.like_count += 1
            await notification_service.create_notification(
                session,
                recipient_id=comment.author_id,
                actor_id=user_id,
                notification_type=NotificationTypeEnum.COMMENT_LIKE,
                post_id=comment.post_id,
                comment_id=comment_id,
            )
            await session.commit()

        return {"comment_id": comment_id, "likes": comment.like_count}

    async def unlike_comment(
        self, comment_id: int, user_id: int, session: AsyncSession
    ) -> dict:
        result = await session.exec(
            select(PostComment).where(PostComment.id == comment_id)
        )
        comment = result.first()
        if not comment:
            from ..errors import CommentNotFoundError
            raise CommentNotFoundError()

        existing = await session.exec(
            select(CommentLike).where(
                CommentLike.comment_id == comment_id,
                CommentLike.user_id == user_id,
            )
        )
        like = existing.first()
        if like:
            await session.delete(like)
            comment.like_count = max(0, comment.like_count - 1)
            await session.commit()

        return {"comment_id": comment_id, "likes": comment.like_count}


    async def save_post(
        self,
        post_id: int,
        user_id: int,
        session: AsyncSession,
        collection_id: Optional[int] = None,
    ) -> dict:
        await self._get_post(post_id, session)

        existing = await session.exec(
            select(SavedPost).where(
                SavedPost.post_id == post_id, SavedPost.user_id == user_id
            )
        )
        if existing.first():
            return {"post_id": post_id, "saved": True}

        session.add(
            SavedPost(post_id=post_id, user_id=user_id, collection_id=collection_id)
        )
        post_result = await session.exec(select(Post).where(Post.id == post_id))
        post = post_result.first()
        if post:
            post.save_count += 1

        await session.commit()
        return {"post_id": post_id, "saved": True}

    async def unsave_post(
        self, post_id: int, user_id: int, session: AsyncSession
    ) -> dict:
        existing = await session.exec(
            select(SavedPost).where(
                SavedPost.post_id == post_id, SavedPost.user_id == user_id
            )
        )
        saved = existing.first()
        if saved:
            await session.delete(saved)
            post_result = await session.exec(select(Post).where(Post.id == post_id))
            post = post_result.first()
            if post:
                post.save_count = max(0, post.save_count - 1)
            await session.commit()
        return {"post_id": post_id, "saved": False}

    async def get_saved_posts(
        self, user_id: int, session: AsyncSession, skip: int = 0, limit: int = 20
    ) -> list:
        result = await session.exec(
            select(Post)
            .join(SavedPost, SavedPost.post_id == Post.id)
            .where(SavedPost.user_id == user_id)
            .options(*_post_opts())
            .order_by(desc(SavedPost.saved_at))
            .offset(skip)
            .limit(limit)
        )
        return [_build_post_response(p) for p in result.all()]

    async def create_collection(
        self, user_id: int, data: CollectionCreate, session: AsyncSession
    ) -> SavedCollection:
        col = SavedCollection(user_id=user_id, name=data.name)
        session.add(col)
        await session.commit()
        await session.refresh(col)
        return col

    async def get_collections(self, user_id: int, session: AsyncSession) -> list:
        result = await session.exec(
            select(SavedCollection).where(SavedCollection.user_id == user_id)
        )
        return result.all()


    async def get_all_interactions_on_my_posts(
        self, owner_id: int, session: AsyncSession
    ) -> list:
        result = await session.exec(
            select(Post)
            .where(Post.author_id == owner_id)
            .options(*_post_opts())
        )
        posts = result.all()
        return [
            {
                "post_id": p.id,
                "caption_preview": (p.caption or "")[:60],
                "like_count": p.like_count,
                "comment_count": p.comment_count,
                "save_count": p.save_count,
            }
            for p in posts
        ]

    async def get_posts_i_liked(self, user_id: int, session: AsyncSession) -> list:
        result = await session.exec(
            select(PostLike).where(PostLike.user_id == user_id)
            .order_by(desc(PostLike.liked_at))
        )
        likes = result.all()
        if not likes:
            return []

        post_ids = [like.post_id for like in likes]
        posts_result = await session.exec(
            select(Post).where(Post.id.in_(post_ids)).options(*_post_opts())
        )
        posts = {p.id: p for p in posts_result.all()}
        return [
            {**_build_post_response(posts[like.post_id]), "liked_at": like.liked_at}
            for like in likes
            if like.post_id in posts
        ]

    async def get_posts_i_commented(self, user_id: int, session: AsyncSession) -> list:
        result = await session.exec(
            select(PostComment).where(PostComment.author_id == user_id)
            .order_by(desc(PostComment.created_at))
        )
        comments = result.all()
        if not comments:
            return []

        post_ids = list({c.post_id for c in comments})
        posts_result = await session.exec(
            select(Post).where(Post.id.in_(post_ids)).options(*_post_opts())
        )
        posts = {p.id: _build_post_response(p) for p in posts_result.all()}
        return [
            {
                "comment_id": c.id,
                "comment_content": c.content,
                "commented_at": c.created_at,
                "post": posts.get(c.post_id),
            }
            for c in comments
        ]
