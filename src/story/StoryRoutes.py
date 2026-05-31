import json
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db.main import get_session
from ..db.models import User
from ..middleware.rate_limit import GENERAL_LIMIT_MIN, WRITE_LIMIT, limiter
from ..users.dependencies import get_current_user
from .StorySchemas import (
    HighlightCreate,
    HighlightDetailOut,
    HighlightOut,
    HighlightUpdate,
    PollCreate,
    PollOut,
    PollVoteCreate,
    QuestionAnswerCreate,
    QuestionAnswerOut,
    QuestionCreate,
    StoryCreate,
    StoryOut,
    StoryReactionCreate,
    StoryReactionOut,
    StoryTrayItem,
    StoryViewerOut,
)
from .StoryService import StoryService

story_router = APIRouter()
story_service = StoryService()


def _parse_json_model(raw: Optional[str], model_cls):
    if not raw:
        return None
    try:
        return model_cls.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {model_cls.__name__}: {exc}",
        )


def _parse_mention_ids(raw: Optional[str]) -> Optional[List[int]]:
    if not raw:
        return None
    try:
        if raw.strip().startswith("["):
            return [int(v) for v in json.loads(raw)]
        return [int(v.strip()) for v in raw.split(",") if v.strip()]
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=400,
            detail="mention_user_ids must be a JSON array or comma-separated integers",
        )


@story_router.post(
    "/stories",
    response_model=StoryOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(WRITE_LIMIT)
async def create_story(
    request: Request,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(default=None),
    location_name: Optional[str] = Form(default=None),
    latitude: Optional[float] = Form(default=None),
    longitude: Optional[float] = Form(default=None),
    close_friends_only: bool = Form(default=False),
    link_url: Optional[str] = Form(default=None),
    poll: Optional[str] = Form(default=None, description="JSON PollCreate"),
    question: Optional[str] = Form(default=None, description="JSON QuestionCreate"),
    mention_user_ids: Optional[str] = Form(
        default=None,
        description="JSON array or comma-separated user IDs",
    ),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    data = StoryCreate(
        caption=caption,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        close_friends_only=close_friends_only,
        link_url=link_url,
        poll=_parse_json_model(poll, PollCreate),
        question=_parse_json_model(question, QuestionCreate),
        mention_user_ids=_parse_mention_ids(mention_user_ids),
    )
    return await story_service.create_story(current_user.id, data, session, file)


@story_router.get("/stories/tray", response_model=List[StoryTrayItem])
async def get_story_tray(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.get_story_tray(
        current_user.id,
        session,
        skip=skip,
        limit=limit,
    )


@story_router.get("/users/{user_id}/stories", response_model=List[StoryOut])
async def get_user_stories(
    user_id: int,
    include_expired: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.get_user_stories(
        user_id,
        current_user.id,
        session,
        include_expired=include_expired,
    )


@story_router.get("/stories/{story_id}", response_model=StoryOut)
async def get_story(
    story_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.get_story(story_id, current_user.id, session)


@story_router.post("/stories/{story_id}/view", response_model=StoryOut)
@limiter.limit(GENERAL_LIMIT_MIN)
async def mark_story_view(
    request: Request,
    story_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.mark_view(story_id, current_user.id, session)


@story_router.get("/stories/{story_id}/viewers", response_model=List[StoryViewerOut])
async def get_story_viewers(
    story_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.get_viewers(story_id, current_user.id, session)


@story_router.delete("/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_LIMIT)
async def delete_story(
    request: Request,
    story_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await story_service.delete_story(story_id, current_user.id, session)


@story_router.post("/stories/{story_id}/reaction", response_model=StoryReactionOut)
@limiter.limit(WRITE_LIMIT)
async def react_to_story(
    request: Request,
    story_id: int,
    data: StoryReactionCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.react_to_story(
        story_id,
        current_user.id,
        data,
        session,
    )


@story_router.delete("/stories/{story_id}/reaction", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_LIMIT)
async def remove_story_reaction(
    request: Request,
    story_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await story_service.remove_reaction(story_id, current_user.id, session)


@story_router.post("/stories/{story_id}/poll/vote", response_model=PollOut)
@limiter.limit(WRITE_LIMIT)
async def vote_story_poll(
    request: Request,
    story_id: int,
    data: PollVoteCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.vote_poll(story_id, current_user.id, data, session)


@story_router.post(
    "/stories/{story_id}/question/answers",
    response_model=QuestionAnswerOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(WRITE_LIMIT)
async def answer_story_question(
    request: Request,
    story_id: int,
    data: QuestionAnswerCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.answer_question(
        story_id,
        current_user.id,
        data,
        session,
    )


@story_router.get(
    "/stories/{story_id}/question/answers",
    response_model=List[QuestionAnswerOut],
)
async def get_story_question_answers(
    story_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.get_question_answers(
        story_id,
        current_user.id,
        session,
    )


@story_router.post(
    "/highlights",
    response_model=HighlightDetailOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(WRITE_LIMIT)
async def create_highlight(
    request: Request,
    data: HighlightCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.create_highlight(current_user.id, data, session)


@story_router.get("/highlights", response_model=List[HighlightOut])
async def get_my_highlights(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.get_my_highlights(current_user.id, session)


@story_router.get("/users/{user_id}/highlights", response_model=List[HighlightOut])
async def get_user_highlights(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.get_user_highlights(user_id, session)


@story_router.get("/highlights/{highlight_id}", response_model=HighlightDetailOut)
async def get_highlight(
    highlight_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.get_highlight(highlight_id, current_user.id, session)


@story_router.patch("/highlights/{highlight_id}", response_model=HighlightDetailOut)
@limiter.limit(WRITE_LIMIT)
async def update_highlight(
    request: Request,
    highlight_id: int,
    data: HighlightUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.update_highlight(
        highlight_id,
        current_user.id,
        data,
        session,
    )


@story_router.delete("/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_LIMIT)
async def delete_highlight(
    request: Request,
    highlight_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await story_service.delete_highlight(highlight_id, current_user.id, session)


@story_router.post(
    "/highlights/{highlight_id}/stories/{story_id}",
    response_model=HighlightDetailOut,
)
@limiter.limit(WRITE_LIMIT)
async def add_story_to_highlight(
    request: Request,
    highlight_id: int,
    story_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.add_story_to_highlight(
        highlight_id,
        story_id,
        current_user.id,
        session,
    )


@story_router.delete(
    "/highlights/{highlight_id}/stories/{story_id}",
    response_model=HighlightDetailOut,
)
@limiter.limit(WRITE_LIMIT)
async def remove_story_from_highlight(
    request: Request,
    highlight_id: int,
    story_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await story_service.remove_story_from_highlight(
        highlight_id,
        story_id,
        current_user.id,
        session,
    )
