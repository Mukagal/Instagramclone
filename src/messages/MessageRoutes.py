from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Query, Request, UploadFile, status,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db.main import get_session
from ..db.models import User
from ..middleware.rate_limit import limiter, WRITE_LIMIT, GENERAL_LIMIT_MIN
from ..users.dependencies import get_current_user
from .MessageSchemas import (
    GroupThreadCreate,
    GroupThreadUpdate,
    MessageOut,
    MessageReactionCreate,
    MessageSend,
    ThreadOut,
)
from .MessageService import MessageService

message_router = APIRouter()
message_service = MessageService()



@message_router.get("/threads", response_model=List[ThreadOut])
async def get_my_threads(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Inbox — all threads the current user is a member of, ordered by latest activity."""
    return await message_service.get_my_threads(
        current_user.id, session, skip=skip, limit=limit
    )


@message_router.post("/threads/dm/{target_id}", response_model=ThreadOut)
@limiter.limit(WRITE_LIMIT)
async def get_or_create_dm(
    request: Request,
    target_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get or create a 1-to-1 DM thread with another user.
    Returns the existing thread if one already exists.
    """
    return await message_service.get_or_create_dm_thread(
        current_user.id, target_id, session
    )


@message_router.post("/threads/group", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_LIMIT)
async def create_group_thread(
    request: Request,
    data: GroupThreadCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new group DM thread. The creator is automatically made admin."""
    return await message_service.create_group_thread(current_user.id, data, session)


@message_router.get("/threads/{thread_id}", response_model=ThreadOut)
async def get_thread(
    thread_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await message_service.get_thread(thread_id, current_user.id, session)


@message_router.patch("/threads/{thread_id}", response_model=ThreadOut)
@limiter.limit(WRITE_LIMIT)
async def update_group_thread(
    request: Request,
    thread_id: int,
    data: GroupThreadUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update group name. Admin only."""
    return await message_service.update_group_thread(
        thread_id, current_user.id, data, session
    )


@message_router.patch("/threads/{thread_id}/cover", response_model=ThreadOut)
@limiter.limit(WRITE_LIMIT)
async def update_group_cover(
    request: Request,
    thread_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upload or replace the group cover image. Admin only."""
    return await message_service.update_group_cover(
        thread_id, current_user.id, file, session
    )


@message_router.post("/threads/{thread_id}/members", response_model=ThreadOut)
@limiter.limit(WRITE_LIMIT)
async def add_members(
    request: Request,
    thread_id: int,
    new_member_ids: List[int],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Add one or more users to a group thread. Admin only."""
    return await message_service.add_members(
        thread_id, current_user.id, new_member_ids, session
    )


@message_router.delete("/threads/{thread_id}/members/{target_id}", response_model=ThreadOut)
@limiter.limit(WRITE_LIMIT)
async def remove_member(
    request: Request,
    thread_id: int,
    target_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Remove a member from a group thread. Admin only."""
    return await message_service.remove_member(
        thread_id, current_user.id, target_id, session
    )


@message_router.post("/threads/{thread_id}/leave")
@limiter.limit(WRITE_LIMIT)
async def leave_thread(
    request: Request,
    thread_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Leave a group thread. The oldest remaining member is promoted if no admins remain."""
    return await message_service.leave_thread(thread_id, current_user.id, session)


@message_router.post("/threads/{thread_id}/members/{target_id}/promote")
@limiter.limit(WRITE_LIMIT)
async def promote_member(
    request: Request,
    thread_id: int,
    target_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Promote a member to admin. Admin only."""
    return await message_service.promote_member(
        thread_id, current_user.id, target_id, session
    )



@message_router.get("/threads/{thread_id}/messages", response_model=List[MessageOut])
async def get_messages(
    thread_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, le=100),
    before_id: Optional[int] = Query(
        default=None,
        description="Cursor-based pagination: fetch messages older than this message ID",
    ),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch messages for a thread in ascending order (oldest first).
    Marks all returned messages as read automatically.
    Use `before_id` for cursor-based pagination (load more / infinite scroll).
    """
    return await message_service.get_messages(
        thread_id, current_user.id, session,
        skip=skip, limit=limit, before_id=before_id,
    )


@message_router.post(
    "/threads/{thread_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(WRITE_LIMIT)
async def send_message(
    request: Request,
    thread_id: int,
    data: MessageSend = Depends(),
    file: Optional[UploadFile] = File(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to a thread.
    Attach an image, video, or voice file via `file`.
    For text-only messages, omit the file field.
    """
    return await message_service.send_message(
        thread_id, current_user.id, data, session, file=file
    )


@message_router.delete("/messages/{message_id}", status_code=status.HTTP_200_OK)
@limiter.limit(WRITE_LIMIT)
async def unsend_message(
    request: Request,
    message_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Unsend (soft-delete) a message. Only the original sender can unsend.
    Content and media are cleared; the message shell remains for read-receipt integrity.
    """
    return await message_service.unsend_message(message_id, current_user.id, session)



@message_router.post("/messages/{message_id}/reaction")
@limiter.limit(WRITE_LIMIT)
async def add_reaction(
    request: Request,
    message_id: int,
    data: MessageReactionCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    React to a message with an emoji.
    One reaction per user per message — calling again replaces the existing emoji.
    """
    return await message_service.add_reaction(
        message_id, current_user.id, data, session
    )


@message_router.delete("/messages/{message_id}/reaction", status_code=status.HTTP_200_OK)
@limiter.limit(WRITE_LIMIT)
async def remove_reaction(
    request: Request,
    message_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Remove your reaction from a message."""
    return await message_service.remove_reaction(message_id, current_user.id, session)