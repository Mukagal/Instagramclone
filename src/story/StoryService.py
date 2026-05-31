import json
import logging
from datetime import datetime
from typing import Optional

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import Config
from ..db.models import (
    Block,
    CloseFriend,
    Follow,
    FollowStatusEnum,
    MediaTypeEnum,
    Story,
    StoryHighlight,
    StoryHighlightItem,
    StoryMention,
    StoryPoll,
    StoryPollVote,
    StoryQuestion,
    StoryQuestionAnswer,
    StoryReaction,
    StoryView,
    User,
    UserProfile,
    NotificationTypeEnum,
)
from ..notifications.NotificationService import notification_service
from .StorySchemas import (
    HighlightCreate,
    HighlightUpdate,
    PollVoteCreate,
    QuestionAnswerCreate,
    StoryCreate,
    StoryReactionCreate,
)

log = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
    api_key=Config.CLOUDINARY_API_KEY,
    api_secret=Config.CLOUDINARY_API_SECRET,
)


def _story_opts():
    return [
        selectinload(Story.author).selectinload(User.profile),
        selectinload(Story.views),
        selectinload(Story.reactions),
        selectinload(Story.mentions),
        selectinload(Story.poll).selectinload(StoryPoll.votes),
        selectinload(Story.question).selectinload(StoryQuestion.answers),
    ]


def _highlight_opts():
    return [
        selectinload(StoryHighlight.items)
        .selectinload(StoryHighlightItem.story)
        .selectinload(Story.author)
        .selectinload(User.profile),
        selectinload(StoryHighlight.items)
        .selectinload(StoryHighlightItem.story)
        .selectinload(Story.views),
        selectinload(StoryHighlight.items)
        .selectinload(StoryHighlightItem.story)
        .selectinload(Story.reactions),
        selectinload(StoryHighlight.items)
        .selectinload(StoryHighlightItem.story)
        .selectinload(Story.poll)
        .selectinload(StoryPoll.votes),
        selectinload(StoryHighlight.items)
        .selectinload(StoryHighlightItem.story)
        .selectinload(Story.question)
        .selectinload(StoryQuestion.answers),
    ]


async def _get_user_info(user_ids: list[int], session: AsyncSession) -> dict[int, dict]:
    if not user_ids:
        return {}
    result = await session.exec(
        select(User.id, User.username, User.is_blue_verified, UserProfile.avatar_path)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(User.id.in_(list(set(user_ids))))
    )
    return {
        row[0]: {
            "username": row[1],
            "is_blue_verified": row[2],
            "avatar_path": row[3],
        }
        for row in result.all()
    }


def _is_active(story: Story) -> bool:
    return story.expires_at > datetime.utcnow()


def _build_author_out(user: Optional[User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_path": user.profile.avatar_path if user.profile else None,
        "is_blue_verified": user.is_blue_verified,
    }


def _build_poll_out(poll: Optional[StoryPoll], viewer_id: Optional[int]) -> Optional[dict]:
    if not poll:
        return None
    my_vote = None
    if viewer_id:
        my_vote = next((v.choice for v in poll.votes if v.voter_id == viewer_id), None)
    return {
        "id": poll.id,
        "question": poll.question,
        "option_a": poll.option_a,
        "option_b": poll.option_b,
        "votes_a": poll.votes_a,
        "votes_b": poll.votes_b,
        "my_vote": my_vote,
    }


def _build_question_out(question: Optional[StoryQuestion]) -> Optional[dict]:
    if not question:
        return None
    return {
        "id": question.id,
        "prompt": question.prompt,
    }


def _build_story_out(story: Story, viewer_id: Optional[int]) -> dict:
    has_viewed = bool(
        viewer_id and any(v.viewer_id == viewer_id for v in story.views)
    )
    my_reaction = None
    if viewer_id:
        my_reaction = next(
            (r.reaction for r in story.reactions if r.reactor_id == viewer_id),
            None,
        )
    return {
        "id": story.id,
        "author_id": story.author_id,
        "author": _build_author_out(story.author),
        "media_path": story.media_path,
        "media_type": story.media_type,
        "thumbnail_path": story.thumbnail_path,
        "duration_seconds": story.duration_seconds,
        "caption": story.caption,
        "location_name": story.location_name,
        "close_friends_only": story.close_friends_only,
        "link_url": story.link_url,
        "view_count": story.view_count,
        "created_at": story.created_at,
        "expires_at": story.expires_at,
        "has_viewed": has_viewed,
        "my_reaction": my_reaction,
        "poll": _build_poll_out(story.poll, viewer_id),
        "question": _build_question_out(story.question),
    }


class StoryService:
    async def _get_story(self, story_id: int, session: AsyncSession) -> Story:
        result = await session.exec(
            select(Story).where(Story.id == story_id).options(*_story_opts())
        )
        story = result.first()
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        return story

    async def _ensure_visible(self, story: Story, viewer_id: int, session: AsyncSession):
        if story.author_id == viewer_id:
            return
        if not _is_active(story):
            raise HTTPException(status_code=404, detail="Story expired")

        block_result = await session.exec(
            select(Block).where(
                ((Block.blocker_id == story.author_id) & (Block.blocked_id == viewer_id))
                | ((Block.blocker_id == viewer_id) & (Block.blocked_id == story.author_id))
            )
        )
        if block_result.first():
            raise HTTPException(status_code=403, detail="Story unavailable")

        if story.close_friends_only:
            cf_result = await session.exec(
                select(CloseFriend).where(
                    CloseFriend.owner_id == story.author_id,
                    CloseFriend.friend_id == viewer_id,
                )
            )
            if not cf_result.first():
                raise HTTPException(status_code=403, detail="Close friends only")
            return

        if story.author and story.author.is_private:
            follow_result = await session.exec(
                select(Follow).where(
                    Follow.follower_id == viewer_id,
                    Follow.followed_id == story.author_id,
                    Follow.status == FollowStatusEnum.ACCEPTED,
                )
            )
            if not follow_result.first():
                raise HTTPException(status_code=403, detail="Private account")

    async def _upload_story_media(self, file: UploadFile) -> tuple[str, MediaTypeEnum]:
        if not file.content_type:
            raise HTTPException(status_code=400, detail="Missing file content type")
        if file.content_type.startswith("image/"):
            media_type = MediaTypeEnum.IMAGE
            resource_type = "image"
        elif file.content_type.startswith("video/"):
            media_type = MediaTypeEnum.VIDEO
            resource_type = "video"
        else:
            raise HTTPException(status_code=400, detail="Stories must be image or video")

        result = cloudinary.uploader.upload(
            file.file,
            folder="stories",
            resource_type=resource_type,
        )
        return result["secure_url"], media_type

    async def create_story(
        self,
        author_id: int,
        data: StoryCreate,
        session: AsyncSession,
        file: UploadFile,
    ) -> dict:
        if data.poll and data.question:
            raise HTTPException(
                status_code=400,
                detail="A story can have either a poll or a question, not both",
            )

        media_path, media_type = await self._upload_story_media(file)
        overlay = {}
        if data.mention_user_ids:
            overlay["mention_user_ids"] = data.mention_user_ids

        story = Story(
            author_id=author_id,
            media_path=media_path,
            media_type=media_type,
            caption=data.caption,
            location_name=data.location_name,
            latitude=data.latitude,
            longitude=data.longitude,
            close_friends_only=data.close_friends_only,
            link_url=data.link_url,
            overlay_data=json.dumps(overlay) if overlay else None,
        )
        session.add(story)
        await session.flush()

        for user_id in data.mention_user_ids or []:
            session.add(StoryMention(story_id=story.id, mentioned_user_id=user_id))
            await notification_service.create_notification(
                session,
                recipient_id=user_id,
                actor_id=author_id,
                notification_type=NotificationTypeEnum.STORY_MENTION,
                story_id=story.id,
            )

        if data.poll:
            session.add(
                StoryPoll(
                    story_id=story.id,
                    question=data.poll.question,
                    option_a=data.poll.option_a,
                    option_b=data.poll.option_b,
                )
            )
        if data.question:
            session.add(
                StoryQuestion(story_id=story.id, prompt=data.question.prompt)
            )

        await session.commit()
        return await self.get_story(story.id, author_id, session)

    async def get_story(self, story_id: int, viewer_id: int, session: AsyncSession) -> dict:
        story = await self._get_story(story_id, session)
        await self._ensure_visible(story, viewer_id, session)
        return _build_story_out(story, viewer_id)

    async def get_user_stories(
        self,
        user_id: int,
        viewer_id: int,
        session: AsyncSession,
        include_expired: bool = False,
    ) -> list:
        statement = (
            select(Story)
            .where(Story.author_id == user_id)
            .options(*_story_opts())
            .order_by(desc(Story.created_at))
        )
        if not include_expired or user_id != viewer_id:
            statement = statement.where(Story.expires_at > datetime.utcnow())
        result = await session.exec(statement)
        stories = []
        for story in result.all():
            try:
                await self._ensure_visible(story, viewer_id, session)
            except HTTPException:
                continue
            stories.append(_build_story_out(story, viewer_id))
        return stories

    async def get_story_tray(
        self,
        user_id: int,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 30,
    ) -> list:
        following_result = await session.exec(
            select(Follow.followed_id).where(
                Follow.follower_id == user_id,
                Follow.status == FollowStatusEnum.ACCEPTED,
            )
        )
        author_ids = list(set([user_id] + list(following_result.all())))

        result = await session.exec(
            select(Story)
            .where(
                Story.author_id.in_(author_ids),
                Story.expires_at > datetime.utcnow(),
            )
            .options(*_story_opts())
            .order_by(desc(Story.created_at))
        )

        grouped: dict[int, list[Story]] = {}
        for story in result.all():
            try:
                await self._ensure_visible(story, user_id, session)
            except HTTPException:
                continue
            grouped.setdefault(story.author_id, []).append(story)

        tray = []
        for author_id, stories in grouped.items():
            latest = max(stories, key=lambda s: s.created_at)
            has_unseen = any(
                not any(v.viewer_id == user_id for v in s.views)
                for s in stories
                if s.author_id != user_id
            )
            tray.append(
                {
                    "user_id": author_id,
                    "username": latest.author.username if latest.author else "",
                    "avatar_path": latest.author.profile.avatar_path
                    if latest.author and latest.author.profile
                    else None,
                    "is_blue_verified": latest.author.is_blue_verified
                    if latest.author
                    else False,
                    "has_unseen": has_unseen,
                    "story_count": len(stories),
                    "latest_story_at": latest.created_at,
                }
            )

        tray.sort(key=lambda item: item["latest_story_at"], reverse=True)
        return tray[skip : skip + limit]

    async def mark_view(self, story_id: int, viewer_id: int, session: AsyncSession) -> dict:
        story = await self._get_story(story_id, session)
        await self._ensure_visible(story, viewer_id, session)

        if story.author_id != viewer_id:
            existing = await session.exec(
                select(StoryView).where(
                    StoryView.story_id == story_id,
                    StoryView.viewer_id == viewer_id,
                )
            )
            if not existing.first():
                session.add(StoryView(story_id=story_id, viewer_id=viewer_id))
                story.view_count += 1
                await session.commit()

        return await self.get_story(story_id, viewer_id, session)

    async def get_viewers(self, story_id: int, owner_id: int, session: AsyncSession) -> list:
        story = await self._get_story(story_id, session)
        if story.author_id != owner_id:
            raise HTTPException(status_code=403, detail="Only the author can see viewers")

        viewer_ids = [v.viewer_id for v in story.views]
        reactions = {r.reactor_id: r.reaction for r in story.reactions}
        info = await _get_user_info(viewer_ids, session)
        return [
            {
                "user_id": v.viewer_id,
                "username": info.get(v.viewer_id, {}).get("username", ""),
                "avatar_path": info.get(v.viewer_id, {}).get("avatar_path"),
                "reaction": reactions.get(v.viewer_id),
                "viewed_at": v.viewed_at,
            }
            for v in sorted(story.views, key=lambda row: row.viewed_at, reverse=True)
        ]

    async def react_to_story(
        self,
        story_id: int,
        reactor_id: int,
        data: StoryReactionCreate,
        session: AsyncSession,
    ) -> dict:
        story = await self._get_story(story_id, session)
        await self._ensure_visible(story, reactor_id, session)
        if story.author_id == reactor_id:
            raise HTTPException(status_code=400, detail="You cannot react to your own story")

        existing = await session.exec(
            select(StoryReaction).where(
                StoryReaction.story_id == story_id,
                StoryReaction.reactor_id == reactor_id,
            )
        )
        reaction = existing.first()
        if reaction:
            reaction.reaction = data.reaction
            reaction.reacted_at = datetime.utcnow()
        else:
            reaction = StoryReaction(
                story_id=story_id,
                reactor_id=reactor_id,
                reaction=data.reaction,
            )
            session.add(reaction)
            await notification_service.create_notification(
                session,
                recipient_id=story.author_id,
                actor_id=reactor_id,
                notification_type=NotificationTypeEnum.STORY_REACTION,
                story_id=story_id,
            )

        await self.mark_view(story_id, reactor_id, session)
        await session.commit()

        info = await _get_user_info([reactor_id], session)
        return {
            "story_id": story_id,
            "reactor_id": reactor_id,
            "reactor_username": info.get(reactor_id, {}).get("username", ""),
            "reactor_avatar": info.get(reactor_id, {}).get("avatar_path"),
            "reaction": reaction.reaction,
            "reacted_at": reaction.reacted_at,
        }

    async def remove_reaction(self, story_id: int, reactor_id: int, session: AsyncSession):
        reaction_result = await session.exec(
            select(StoryReaction).where(
                StoryReaction.story_id == story_id,
                StoryReaction.reactor_id == reactor_id,
            )
        )
        reaction = reaction_result.first()
        if reaction:
            await session.delete(reaction)
            await session.commit()

    async def vote_poll(
        self,
        story_id: int,
        voter_id: int,
        data: PollVoteCreate,
        session: AsyncSession,
    ) -> dict:
        story = await self._get_story(story_id, session)
        await self._ensure_visible(story, voter_id, session)
        if not story.poll:
            raise HTTPException(status_code=404, detail="Story poll not found")

        existing_result = await session.exec(
            select(StoryPollVote).where(
                StoryPollVote.poll_id == story.poll.id,
                StoryPollVote.voter_id == voter_id,
            )
        )
        existing = existing_result.first()
        if existing:
            if existing.choice == data.choice:
                return _build_poll_out(story.poll, voter_id)
            if existing.choice == "a":
                story.poll.votes_a -= 1
            else:
                story.poll.votes_b -= 1
            existing.choice = data.choice
            existing.voted_at = datetime.utcnow()
        else:
            session.add(
                StoryPollVote(
                    poll_id=story.poll.id,
                    voter_id=voter_id,
                    choice=data.choice,
                )
            )

        if data.choice == "a":
            story.poll.votes_a += 1
        else:
            story.poll.votes_b += 1

        await self.mark_view(story_id, voter_id, session)
        await session.commit()
        story = await self._get_story(story_id, session)
        return _build_poll_out(story.poll, voter_id)

    async def answer_question(
        self,
        story_id: int,
        responder_id: int,
        data: QuestionAnswerCreate,
        session: AsyncSession,
    ) -> dict:
        story = await self._get_story(story_id, session)
        await self._ensure_visible(story, responder_id, session)
        if not story.question:
            raise HTTPException(status_code=404, detail="Story question not found")

        answer = StoryQuestionAnswer(
            question_id=story.question.id,
            responder_id=responder_id,
            answer_text=data.answer_text,
        )
        session.add(answer)
        await self.mark_view(story_id, responder_id, session)
        await session.commit()

        info = await _get_user_info([responder_id], session)
        return {
            "id": answer.id,
            "responder_id": responder_id,
            "responder_username": info.get(responder_id, {}).get("username", ""),
            "responder_avatar": info.get(responder_id, {}).get("avatar_path"),
            "answer_text": answer.answer_text,
            "answered_at": answer.answered_at,
        }

    async def get_question_answers(
        self,
        story_id: int,
        owner_id: int,
        session: AsyncSession,
    ) -> list:
        story = await self._get_story(story_id, session)
        if story.author_id != owner_id:
            raise HTTPException(status_code=403, detail="Only the author can see answers")
        if not story.question:
            raise HTTPException(status_code=404, detail="Story question not found")

        responder_ids = [a.responder_id for a in story.question.answers]
        info = await _get_user_info(responder_ids, session)
        return [
            {
                "id": a.id,
                "responder_id": a.responder_id,
                "responder_username": info.get(a.responder_id, {}).get("username", ""),
                "responder_avatar": info.get(a.responder_id, {}).get("avatar_path"),
                "answer_text": a.answer_text,
                "answered_at": a.answered_at,
            }
            for a in sorted(
                story.question.answers,
                key=lambda row: row.answered_at,
                reverse=True,
            )
        ]

    async def delete_story(self, story_id: int, owner_id: int, session: AsyncSession):
        story = await self._get_story(story_id, session)
        if story.author_id != owner_id:
            raise HTTPException(status_code=403, detail="Only the author can delete this story")
        await session.delete(story)
        await session.commit()

    async def create_highlight(
        self,
        user_id: int,
        data: HighlightCreate,
        session: AsyncSession,
    ) -> dict:
        highlight = StoryHighlight(user_id=user_id, title=data.title)
        session.add(highlight)
        await session.flush()

        for position, story_id in enumerate(data.story_ids or []):
            story = await self._get_story(story_id, session)
            if story.author_id != user_id:
                raise HTTPException(status_code=403, detail="Cannot highlight another user's story")
            session.add(
                StoryHighlightItem(
                    highlight_id=highlight.id,
                    story_id=story_id,
                    position=position,
                )
            )
            if position == 0:
                highlight.cover_path = story.thumbnail_path or story.media_path

        await session.commit()
        return await self.get_highlight(highlight.id, user_id, session)

    async def get_my_highlights(self, user_id: int, session: AsyncSession) -> list:
        result = await session.exec(
            select(StoryHighlight)
            .where(StoryHighlight.user_id == user_id)
            .options(*_highlight_opts())
            .order_by(desc(StoryHighlight.created_at))
        )
        return [_build_highlight_out(h) for h in result.all()]

    async def get_user_highlights(self, user_id: int, session: AsyncSession) -> list:
        return await self.get_my_highlights(user_id, session)

    async def get_highlight(
        self,
        highlight_id: int,
        viewer_id: int,
        session: AsyncSession,
    ) -> dict:
        result = await session.exec(
            select(StoryHighlight)
            .where(StoryHighlight.id == highlight_id)
            .options(*_highlight_opts())
        )
        highlight = result.first()
        if not highlight:
            raise HTTPException(status_code=404, detail="Highlight not found")

        stories = []
        for item in sorted(highlight.items, key=lambda row: row.position):
            if item.story:
                try:
                    await self._ensure_visible(item.story, viewer_id, session)
                except HTTPException:
                    continue
                stories.append(_build_story_out(item.story, viewer_id))

        out = _build_highlight_out(highlight)
        out["stories"] = stories
        return out

    async def update_highlight(
        self,
        highlight_id: int,
        user_id: int,
        data: HighlightUpdate,
        session: AsyncSession,
    ) -> dict:
        highlight = await self._get_owned_highlight(highlight_id, user_id, session)
        if data.title is not None:
            highlight.title = data.title
        await session.commit()
        return await self.get_highlight(highlight_id, user_id, session)

    async def delete_highlight(self, highlight_id: int, user_id: int, session: AsyncSession):
        highlight = await self._get_owned_highlight(highlight_id, user_id, session)
        await session.delete(highlight)
        await session.commit()

    async def add_story_to_highlight(
        self,
        highlight_id: int,
        story_id: int,
        user_id: int,
        session: AsyncSession,
    ) -> dict:
        highlight = await self._get_owned_highlight(highlight_id, user_id, session)
        story = await self._get_story(story_id, session)
        if story.author_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot highlight another user's story")

        existing = await session.exec(
            select(StoryHighlightItem).where(
                StoryHighlightItem.highlight_id == highlight_id,
                StoryHighlightItem.story_id == story_id,
            )
        )
        if not existing.first():
            position = len(highlight.items)
            session.add(
                StoryHighlightItem(
                    highlight_id=highlight_id,
                    story_id=story_id,
                    position=position,
                )
            )
            if not highlight.cover_path:
                highlight.cover_path = story.thumbnail_path or story.media_path
            await session.commit()
        return await self.get_highlight(highlight_id, user_id, session)

    async def remove_story_from_highlight(
        self,
        highlight_id: int,
        story_id: int,
        user_id: int,
        session: AsyncSession,
    ) -> dict:
        await self._get_owned_highlight(highlight_id, user_id, session)
        result = await session.exec(
            select(StoryHighlightItem).where(
                StoryHighlightItem.highlight_id == highlight_id,
                StoryHighlightItem.story_id == story_id,
            )
        )
        item = result.first()
        if item:
            await session.delete(item)
            await session.commit()
        return await self.get_highlight(highlight_id, user_id, session)

    async def _get_owned_highlight(
        self,
        highlight_id: int,
        user_id: int,
        session: AsyncSession,
    ) -> StoryHighlight:
        result = await session.exec(
            select(StoryHighlight)
            .where(
                StoryHighlight.id == highlight_id,
                StoryHighlight.user_id == user_id,
            )
            .options(*_highlight_opts())
        )
        highlight = result.first()
        if not highlight:
            raise HTTPException(status_code=404, detail="Highlight not found")
        return highlight


def _build_highlight_out(highlight: StoryHighlight) -> dict:
    return {
        "id": highlight.id,
        "user_id": highlight.user_id,
        "title": highlight.title,
        "cover_path": highlight.cover_path,
        "story_count": len(highlight.items),
        "created_at": highlight.created_at,
    }
