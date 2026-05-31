import io
import base64
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    Query, Request, UploadFile, status,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import Config
from ..db.main import get_session
from ..db.models import User
from ..middleware.rate_limit import limiter, WRITE_LIMIT, GENERAL_LIMIT_MIN
from ..tasks.moderation_task import moderate_image
from ..users.dependencies import get_current_user, get_optional_user
from .PostSchemas import (
    CollectionCreate,
    CollectionOut,
    CommentCreate,
    CommentLikeResponse,
    CommentResponse,
    CommentUpdate,
    LikeResponse,
    PostCreate,
    PostInteractionSummary,
    PostResponse,
    PostUpdate,
    SaveResponse,
    SortBy,
)
from .PostService import PostService

post_router = APIRouter()
post_service = PostService()


@post_router.get("/feed", response_model=List[PostResponse])
async def get_explore_feed(
    sort_by: SortBy = Query(default=SortBy.latest),
    keyword: Optional[str] = Query(default=None, description="Search in caption"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Explore feed — all public non-flagged posts."""
    return await post_service.get_feed(
        session,
        sort_by=sort_by,
        keyword=keyword,
        skip=skip,
        limit=limit,
        current_user_id=current_user.id if current_user else None,
    )


@post_router.get("/feed/following", response_model=List[PostResponse])
async def get_following_feed(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Home feed — posts from accounts you follow, newest first."""
    return await post_service.get_following_feed(
        current_user.id, session, skip=skip, limit=limit
    )



@post_router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_LIMIT)
async def create_post(
    request: Request,
    caption: Optional[str] = Form(default=None),
    location_name: Optional[str] = Form(default=None),
    hide_like_count: bool = Form(default=False),
    disable_comments: bool = Form(default=False),
    tagged_user_ids: Optional[str] = Form(default=None, description="Comma-separated user IDs"),
    files: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create a post with 1–10 media files.
    A single file → IMAGE post.  Multiple files → CAROUSEL post.
    tagged_user_ids is a comma-separated string e.g. "3,17,42".
    """
    refreshed_files = []
    all_bytes = []
    for f in files:
        if not (f.content_type.startswith("image/") or f.content_type.startswith("video/")):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {f.content_type}")
        raw = await f.read()
        all_bytes.append(raw)
        f.file = io.BytesIO(raw)
        refreshed_files.append(f)

    tag_ids = []
    if tagged_user_ids:
        try:
            tag_ids = [int(x.strip()) for x in tagged_user_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="tagged_user_ids must be comma-separated integers")

    post_data = PostCreate(
        caption=caption,
        location_name=location_name,
        hide_like_count=hide_like_count,
        disable_comments=disable_comments,
    )

    post = await post_service.create_post(
        current_user.id, post_data, session,
        files=refreshed_files,
        tagged_user_ids=tag_ids,
    )

    for raw, f in zip(all_bytes, files):
        if f.content_type and f.content_type.startswith("image/"):
            b64 = base64.b64encode(raw).decode()
            moderate_image.delay(post["id"], b64, Config.DATABASE_URL)

    return post


@post_router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    session: AsyncSession = Depends(get_session),
    _: Optional[User] = Depends(get_optional_user),
):
    return await post_service.get_post(post_id, session)


@post_router.patch("/posts/{post_id}", response_model=PostResponse)
@limiter.limit(WRITE_LIMIT)
async def update_post(
    request: Request,
    post_id: int,
    update_data: PostUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.update_post(post_id, current_user.id, update_data, session)


@post_router.post("/posts/{post_id}/archive")
@limiter.limit(WRITE_LIMIT)
async def toggle_archive_post(
    request: Request,
    post_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Toggle archive state. Archived posts are hidden from the profile grid."""
    return await post_service.archive_post(post_id, current_user.id, session)


@post_router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_LIMIT)
async def delete_post(
    request: Request,
    post_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await post_service.delete_post(post_id, current_user.id, session)


@post_router.get("/users/{user_id}/posts", response_model=List[PostResponse])
async def get_user_posts(
    user_id: int,
    sort_by: SortBy = Query(default=SortBy.latest),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    return await post_service.get_user_posts(
        user_id, session,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
        viewer_id=current_user.id if current_user else None,
    )


@post_router.get("/users/me/posts/archived", response_model=List[PostResponse])
async def get_my_archived_posts(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Only visible to the account owner."""
    return await post_service.get_archived_posts(current_user.id, session)



@post_router.post("/posts/{post_id}/like", response_model=LikeResponse)
@limiter.limit(WRITE_LIMIT)
async def like_post(
    request: Request,
    post_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.like_post(post_id, current_user.id, session)


@post_router.delete("/posts/{post_id}/like", response_model=LikeResponse)
@limiter.limit(WRITE_LIMIT)
async def unlike_post(
    request: Request,
    post_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.unlike_post(post_id, current_user.id, session)


@post_router.get("/posts/{post_id}/likes")
async def get_post_likers(
    post_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Only the post author can see the full liker list."""
    return await post_service.get_post_likers(post_id, current_user.id, session)


@post_router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_comments(
    post_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    include_replies: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    _: Optional[User] = Depends(get_optional_user),
):
    return await post_service.get_comments(
        post_id, session,
        skip=skip, limit=limit,
        include_replies=include_replies,
    )


@post_router.get("/comments/{comment_id}/replies", response_model=List[CommentResponse])
async def get_replies(
    comment_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    _: Optional[User] = Depends(get_optional_user),
):
    return await post_service.get_replies(comment_id, session, skip=skip, limit=limit)


@post_router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(WRITE_LIMIT)
async def add_comment(
    request: Request,
    post_id: int,
    comment_data: CommentCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Add a comment. Set parent_id to reply to an existing top-level comment.
    """
    return await post_service.add_comment(post_id, current_user.id, comment_data, session)


@post_router.patch("/comments/{comment_id}", response_model=CommentResponse)
@limiter.limit(WRITE_LIMIT)
async def update_comment(
    request: Request,
    comment_id: int,
    update_data: CommentUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.update_comment(comment_id, current_user.id, update_data, session)


@post_router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_LIMIT)
async def delete_comment(
    request: Request,
    comment_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await post_service.delete_comment(comment_id, current_user.id, session)



@post_router.post("/comments/{comment_id}/like", response_model=CommentLikeResponse)
@limiter.limit(WRITE_LIMIT)
async def like_comment(
    request: Request,
    comment_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.like_comment(comment_id, current_user.id, session)


@post_router.delete("/comments/{comment_id}/like", response_model=CommentLikeResponse)
@limiter.limit(WRITE_LIMIT)
async def unlike_comment(
    request: Request,
    comment_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.unlike_comment(comment_id, current_user.id, session)


@post_router.post("/posts/{post_id}/save", response_model=SaveResponse)
@limiter.limit(WRITE_LIMIT)
async def save_post(
    request: Request,
    post_id: int,
    collection_id: Optional[int] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bookmark a post. Optionally assign it to a collection."""
    return await post_service.save_post(
        post_id, current_user.id, session, collection_id=collection_id
    )


@post_router.delete("/posts/{post_id}/save", response_model=SaveResponse)
@limiter.limit(WRITE_LIMIT)
async def unsave_post(
    request: Request,
    post_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.unsave_post(post_id, current_user.id, session)


@post_router.get("/users/me/saved", response_model=List[PostResponse])
async def get_saved_posts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.get_saved_posts(current_user.id, session, skip=skip, limit=limit)


@post_router.post("/collections", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_LIMIT)
async def create_collection(
    request: Request,
    data: CollectionCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.create_collection(current_user.id, data, session)


@post_router.get("/collections", response_model=List[CollectionOut])
async def get_my_collections(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.get_collections(current_user.id, session)



@post_router.get("/me/posts/interactions", response_model=List[PostInteractionSummary])
async def my_posts_interactions(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Per-post like / comment / save breakdown for the current user's posts."""
    return await post_service.get_all_interactions_on_my_posts(current_user.id, session)


@post_router.get("/me/liked-posts", response_model=List[PostResponse])
async def posts_i_liked(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.get_posts_i_liked(current_user.id, session)


@post_router.get("/me/commented-posts")
async def posts_i_commented(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await post_service.get_posts_i_commented(current_user.id, session)