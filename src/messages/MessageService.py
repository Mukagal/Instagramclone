import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

import cloudinary
import cloudinary.uploader

from ..config import Config
from ..db.models import (
    Block,
    DirectMessage,
    DirectThread,
    Follow,
    FollowStatusEnum,
    MessageReaction,
    MessageReadReceipt,
    MessageTypeEnum,
    ThreadMember,
    User,
    UserProfile,
)
from .MessageSchemas import GroupThreadCreate, GroupThreadUpdate, MessageReactionCreate, MessageSend

log = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
    api_key=Config.CLOUDINARY_API_KEY,
    api_secret=Config.CLOUDINARY_API_SECRET,
)



def _thread_opts():
    return [
        selectinload(DirectThread.members),
        selectinload(DirectThread.messages).selectinload(DirectMessage.reactions),
        selectinload(DirectThread.messages).selectinload(DirectMessage.read_receipts),
    ]


async def _get_member_info(user_ids: list[int], session: AsyncSession) -> dict[int, dict]:
    """Batch-fetch username + avatar for a list of user IDs."""
    result = await session.exec(
        select(User.id, User.username, UserProfile.avatar_path)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(User.id.in_(user_ids))
    )
    return {
        row[0]: {"username": row[1], "avatar_path": row[2]}
        for row in result.all()
    }


async def _build_thread_out(
    thread: DirectThread,
    current_user_id: int,
    session: AsyncSession,
) -> dict:
    member_ids = [m.user_id for m in thread.members]
    info = await _get_member_info(member_ids, session)

    members_out = [
        {
            "user_id": m.user_id,
            "username": info.get(m.user_id, {}).get("username", ""),
            "avatar_path": info.get(m.user_id, {}).get("avatar_path"),
            "is_admin": m.is_admin,
            "joined_at": m.joined_at,
        }
        for m in thread.members
        if m.left_at is None
    ]

    last_msg = None
    last_preview = None
    if thread.messages:
        last_msg = sorted(thread.messages, key=lambda m: m.sent_at)[-1]
        if last_msg.is_deleted:
            last_preview = "Message deleted"
        elif last_msg.message_type == MessageTypeEnum.TEXT:
            last_preview = (last_msg.content or "")[:80]
        elif last_msg.message_type == MessageTypeEnum.IMAGE:
            last_preview = "Photo"
        elif last_msg.message_type == MessageTypeEnum.VIDEO:
            last_preview = "Video"
        elif last_msg.message_type == MessageTypeEnum.REEL_SHARE:
            last_preview = "Reel"
        elif last_msg.message_type == MessageTypeEnum.POST_SHARE:
            last_preview = "Post"
        elif last_msg.message_type == MessageTypeEnum.VOICE:
            last_preview = "Voice message"
        elif last_msg.message_type == MessageTypeEnum.GIF:
            last_preview = "GIF"
        else:
            last_preview = "Message"

    my_member = next((m for m in thread.members if m.user_id == current_user_id), None)
    last_read = my_member.last_read_at if my_member else None
    unread = sum(
        1 for m in thread.messages
        if m.sender_id != current_user_id
        and not m.is_deleted
        and (last_read is None or m.sent_at > last_read)
    )

    return {
        "id": thread.id,
        "is_group": thread.is_group,
        "group_name": thread.group_name,
        "group_cover_path": thread.group_cover_path,
        "created_at": thread.created_at,
        "last_message_at": thread.last_message_at,
        "members": members_out,
        "last_message_preview": last_preview,
        "unread_count": unread,
    }


async def _build_message_out(
    msg: DirectMessage,
    info: dict[int, dict],
) -> dict:
    sender_info = info.get(msg.sender_id, {})

    reactions_out = [
        {
            "user_id": r.user_id,
            "username": info.get(r.user_id, {}).get("username", ""),
            "emoji": r.emoji,
            "reacted_at": r.reacted_at,
        }
        for r in (msg.reactions or [])
    ]
    receipts_out = [
        {
            "reader_id": rr.reader_id,
            "username": info.get(rr.reader_id, {}).get("username", ""),
            "read_at": rr.read_at,
        }
        for rr in (msg.read_receipts or [])
    ]

    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_id": msg.sender_id,
        "sender_username": sender_info.get("username", ""),
        "sender_avatar": sender_info.get("avatar_path"),
        "message_type": msg.message_type,
        "content": msg.content if not msg.is_deleted else None,
        "media_path": msg.media_path if not msg.is_deleted else None,
        "shared_post_id": msg.shared_post_id,
        "shared_reel_id": msg.shared_reel_id,
        "story_reply_id": msg.story_reply_id,
        "reply_to_message_id": msg.reply_to_message_id,
        "is_disappearing": msg.is_disappearing,
        "is_deleted": msg.is_deleted,
        "sent_at": msg.sent_at,
        "reactions": reactions_out,
        "read_receipts": receipts_out,
    }



class MessageService:


    async def _get_thread(
        self, thread_id: int, session: AsyncSession
    ) -> DirectThread:
        result = await session.exec(
            select(DirectThread)
            .where(DirectThread.id == thread_id)
            .options(*_thread_opts())
        )
        thread = result.first()
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        return thread

    async def _require_member(
        self, thread_id: int, user_id: int, session: AsyncSession
    ) -> ThreadMember:
        result = await session.exec(
            select(ThreadMember).where(
                ThreadMember.thread_id == thread_id,
                ThreadMember.user_id == user_id,
                ThreadMember.left_at == None,
            )
        )
        member = result.first()
        if not member:
            raise HTTPException(status_code=403, detail="You are not a member of this thread")
        return member

    async def _require_admin(
        self, thread_id: int, user_id: int, session: AsyncSession
    ) -> ThreadMember:
        member = await self._require_member(thread_id, user_id, session)
        if not member.is_admin:
            raise HTTPException(status_code=403, detail="Admin permission required")
        return member

    async def _check_not_blocked(
        self, user_a: int, user_b: int, session: AsyncSession
    ):
        result = await session.exec(
            select(Block).where(
                ((Block.blocker_id == user_a) & (Block.blocked_id == user_b))
                | ((Block.blocker_id == user_b) & (Block.blocked_id == user_a))
            )
        )
        if result.first():
            raise HTTPException(status_code=403, detail="Cannot message this user")


    async def get_or_create_dm_thread(
        self, user_id: int, target_id: int, session: AsyncSession
    ) -> dict:
        """
        Returns existing 1-to-1 thread between two users, or creates one.
        Enforces: no self-DM, no block, must follow or be followed
        (matching Instagram's DM rules).
        """
        if user_id == target_id:
            raise HTTPException(status_code=400, detail="Cannot DM yourself")

        await self._check_not_blocked(user_id, target_id, session)

        follow_result = await session.exec(
            select(Follow).where(
                (
                    (Follow.follower_id == user_id) & (Follow.followed_id == target_id)
                    & (Follow.status == FollowStatusEnum.ACCEPTED)
                ) | (
                    (Follow.follower_id == target_id) & (Follow.followed_id == user_id)
                    & (Follow.status == FollowStatusEnum.ACCEPTED)
                )
            )
        )
        if not follow_result.first():
            raise HTTPException(
                status_code=403,
                detail="You can only DM users you follow or who follow you"
            )

        result = await session.exec(
            select(DirectThread)
            .join(ThreadMember, ThreadMember.thread_id == DirectThread.id)
            .where(
                DirectThread.is_group == False,
                ThreadMember.user_id == user_id,
                ThreadMember.left_at == None,
            )
            .options(*_thread_opts())
        )
        for thread in result.all():
            other_ids = {m.user_id for m in thread.members if m.left_at is None}
            if other_ids == {user_id, target_id}:
                return await _build_thread_out(thread, user_id, session)

        thread = DirectThread(is_group=False)
        session.add(thread)
        await session.flush()

        session.add(ThreadMember(thread_id=thread.id, user_id=user_id, is_admin=False))
        session.add(ThreadMember(thread_id=thread.id, user_id=target_id, is_admin=False))

        await session.commit()
        return await _build_thread_out(
            await self._get_thread(thread.id, session), user_id, session
        )

    async def create_group_thread(
        self, creator_id: int, data: GroupThreadCreate, session: AsyncSession
    ) -> dict:
        if creator_id in data.member_ids:
            data.member_ids.remove(creator_id)  

        all_ids = list(set(data.member_ids))
        if len(all_ids) < 1:
            raise HTTPException(status_code=400, detail="A group needs at least one other member")
        if len(all_ids) > 31:
            raise HTTPException(status_code=400, detail="Group DMs support up to 32 members")

        thread = DirectThread(
            is_group=True,
            group_name=data.name,
            created_by=creator_id,
        )
        session.add(thread)
        await session.flush()

        session.add(ThreadMember(thread_id=thread.id, user_id=creator_id, is_admin=True))
        for uid in all_ids:
            session.add(ThreadMember(thread_id=thread.id, user_id=uid, is_admin=False))

        await session.commit()
        return await _build_thread_out(
            await self._get_thread(thread.id, session), creator_id, session
        )

    async def get_my_threads(
        self, user_id: int, session: AsyncSession, skip: int = 0, limit: int = 30
    ) -> list:
        result = await session.exec(
            select(DirectThread)
            .join(ThreadMember, ThreadMember.thread_id == DirectThread.id)
            .where(
                ThreadMember.user_id == user_id,
                ThreadMember.left_at == None,
            )
            .options(*_thread_opts())
            .order_by(desc(DirectThread.last_message_at))
            .offset(skip)
            .limit(limit)
        )
        threads = result.all()
        return [await _build_thread_out(t, user_id, session) for t in threads]

    async def get_thread(
        self, thread_id: int, user_id: int, session: AsyncSession
    ) -> dict:
        await self._require_member(thread_id, user_id, session)
        thread = await self._get_thread(thread_id, session)
        return await _build_thread_out(thread, user_id, session)

    async def update_group_thread(
        self, thread_id: int, user_id: int, data: GroupThreadUpdate, session: AsyncSession
    ) -> dict:
        thread = await self._get_thread(thread_id, session)
        if not thread.is_group:
            raise HTTPException(status_code=400, detail="Not a group thread")
        await self._require_admin(thread_id, user_id, session)

        if data.name is not None:
            thread.group_name = data.name
        await session.commit()
        return await _build_thread_out(
            await self._get_thread(thread_id, session), user_id, session
        )

    async def update_group_cover(
        self, thread_id: int, user_id: int, file: UploadFile, session: AsyncSession
    ) -> dict:
        thread = await self._get_thread(thread_id, session)
        if not thread.is_group:
            raise HTTPException(status_code=400, detail="Not a group thread")
        await self._require_admin(thread_id, user_id, session)

        result = cloudinary.uploader.upload(
            file.file,
            folder="group_covers",
            public_id=f"group_{thread_id}",
            overwrite=True,
            transformation=[{"width": 300, "height": 300, "crop": "fill"}],
        )
        thread.group_cover_path = result["secure_url"]
        await session.commit()
        return await _build_thread_out(
            await self._get_thread(thread_id, session), user_id, session
        )


    async def add_members(
        self, thread_id: int, user_id: int, new_member_ids: list[int], session: AsyncSession
    ) -> dict:
        thread = await self._get_thread(thread_id, session)
        if not thread.is_group:
            raise HTTPException(status_code=400, detail="Cannot add members to a DM thread")
        await self._require_admin(thread_id, user_id, session)

        current_ids = {m.user_id for m in thread.members if m.left_at is None}
        for uid in set(new_member_ids):
            if uid not in current_ids:
                session.add(ThreadMember(thread_id=thread_id, user_id=uid, is_admin=False))

        await session.commit()
        return await _build_thread_out(
            await self._get_thread(thread_id, session), user_id, session
        )

    async def remove_member(
        self, thread_id: int, admin_id: int, target_id: int, session: AsyncSession
    ) -> dict:
        await self._require_admin(thread_id, admin_id, session)
        result = await session.exec(
            select(ThreadMember).where(
                ThreadMember.thread_id == thread_id,
                ThreadMember.user_id == target_id,
            )
        )
        member = result.first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        member.left_at = datetime.utcnow()
        await session.commit()
        return await _build_thread_out(
            await self._get_thread(thread_id, session), admin_id, session
        )

    async def leave_thread(
        self, thread_id: int, user_id: int, session: AsyncSession
    ) -> dict:
        thread = await self._get_thread(thread_id, session)
        if not thread.is_group:
            raise HTTPException(status_code=400, detail="Cannot leave a 1-to-1 DM")

        member = await self._require_member(thread_id, user_id, session)
        member.left_at = datetime.utcnow()

        active = [m for m in thread.members if m.left_at is None and m.user_id != user_id]
        admins = [m for m in active if m.is_admin]
        if not admins and active:
            active.sort(key=lambda m: m.joined_at)
            active[0].is_admin = True

        await session.commit()
        return {"message": "Left the group"}

    async def promote_member(
        self, thread_id: int, admin_id: int, target_id: int, session: AsyncSession
    ) -> dict:
        await self._require_admin(thread_id, admin_id, session)
        result = await session.exec(
            select(ThreadMember).where(
                ThreadMember.thread_id == thread_id,
                ThreadMember.user_id == target_id,
                ThreadMember.left_at == None,
            )
        )
        member = result.first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        member.is_admin = True
        await session.commit()
        return {"message": f"User {target_id} promoted to admin"}


    async def send_message(
        self,
        thread_id: int,
        sender_id: int,
        data: MessageSend,
        session: AsyncSession,
        file: Optional[UploadFile] = None,
    ) -> dict:
        thread = await self._get_thread(thread_id, session)
        await self._require_member(thread_id, sender_id, session)

        if not thread.is_group:
            other = next(
                (m.user_id for m in thread.members if m.user_id != sender_id), None
            )
            if other:
                await self._check_not_blocked(sender_id, other, session)

        if data.message_type == MessageTypeEnum.TEXT and not data.content:
            raise HTTPException(status_code=400, detail="Text messages require content")

        media_path = None
        if file:
            folder = (
                "dm_voice" if data.message_type == MessageTypeEnum.VOICE
                else "dm_videos" if data.message_type == MessageTypeEnum.VIDEO
                else "dm_images"
            )
            result = cloudinary.uploader.upload(file.file, folder=folder)
            media_path = result["secure_url"]

        if data.shared_post_id and data.shared_reel_id:
            raise HTTPException(
                status_code=400, detail="Share either a post or a reel, not both"
            )

        msg = DirectMessage(
            thread_id=thread_id,
            sender_id=sender_id,
            message_type=data.message_type,
            content=data.content,
            media_path=media_path,
            shared_post_id=data.shared_post_id,
            shared_reel_id=data.shared_reel_id,
            story_reply_id=data.story_reply_id,
            reply_to_message_id=data.reply_to_message_id,
            is_disappearing=data.is_disappearing,
        )
        session.add(msg)

        thread.last_message_at = datetime.utcnow()

        await session.flush()

        session.add(MessageReadReceipt(message_id=msg.id, reader_id=sender_id))

        await session.commit()

        all_ids = list({sender_id} | {m.user_id for m in thread.members})
        info = await _get_member_info(all_ids, session)

        msg_result = await session.exec(
            select(DirectMessage)
            .where(DirectMessage.id == msg.id)
            .options(
                selectinload(DirectMessage.reactions),
                selectinload(DirectMessage.read_receipts),
            )
        )
        return await _build_message_out(msg_result.first(), info)

    async def get_messages(
        self,
        thread_id: int,
        user_id: int,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 30,
        before_id: Optional[int] = None,  
    ) -> list:
        await self._require_member(thread_id, user_id, session)

        statement = (
            select(DirectMessage)
            .where(DirectMessage.thread_id == thread_id)
            .options(
                selectinload(DirectMessage.reactions),
                selectinload(DirectMessage.read_receipts),
            )
            .order_by(desc(DirectMessage.sent_at))
        )
        if before_id:
            cursor_result = await session.exec(
                select(DirectMessage.sent_at).where(DirectMessage.id == before_id)
            )
            cursor_ts = cursor_result.first()
            if cursor_ts:
                statement = statement.where(DirectMessage.sent_at < cursor_ts)

        statement = statement.offset(skip).limit(limit)
        result = await session.exec(statement)
        messages = result.all()

        all_ids = list({m.sender_id for m in messages})
        for m in messages:
            for r in m.reactions:
                all_ids.append(r.user_id)
            for rr in m.read_receipts:
                all_ids.append(rr.reader_id)
        info = await _get_member_info(list(set(all_ids)), session)

        for msg in messages:
            if msg.sender_id != user_id:
                existing = await session.exec(
                    select(MessageReadReceipt).where(
                        MessageReadReceipt.message_id == msg.id,
                        MessageReadReceipt.reader_id == user_id,
                    )
                )
                if not existing.first():
                    session.add(MessageReadReceipt(message_id=msg.id, reader_id=user_id))

        member_result = await session.exec(
            select(ThreadMember).where(
                ThreadMember.thread_id == thread_id,
                ThreadMember.user_id == user_id,
            )
        )
        member = member_result.first()
        if member:
            member.last_read_at = datetime.utcnow()

        await session.commit()

        return [await _build_message_out(m, info) for m in reversed(messages)]

    async def unsend_message(
        self, message_id: int, user_id: int, session: AsyncSession
    ) -> dict:
        """Soft-delete — marks is_deleted=True, hides content."""
        result = await session.exec(
            select(DirectMessage).where(DirectMessage.id == message_id)
        )
        msg = result.first()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        if msg.sender_id != user_id:
            raise HTTPException(status_code=403, detail="You can only unsend your own messages")
        msg.is_deleted = True
        msg.content = None
        msg.media_path = None
        await session.commit()
        return {"message_id": message_id, "unsent": True}


    async def add_reaction(
        self,
        message_id: int,
        user_id: int,
        data: MessageReactionCreate,
        session: AsyncSession,
    ) -> dict:
        result = await session.exec(
            select(DirectMessage).where(DirectMessage.id == message_id)
        )
        msg = result.first()
        if not msg or msg.is_deleted:
            raise HTTPException(status_code=404, detail="Message not found")

        await self._require_member(msg.thread_id, user_id, session)

        existing = await session.exec(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
            )
        )
        reaction = existing.first()
        if reaction:
            reaction.emoji = data.emoji
            reaction.reacted_at = datetime.utcnow()
        else:
            reaction = MessageReaction(
                message_id=message_id, user_id=user_id, emoji=data.emoji
            )
            session.add(reaction)

        await session.commit()
        return {"message_id": message_id, "emoji": data.emoji}

    async def remove_reaction(
        self, message_id: int, user_id: int, session: AsyncSession
    ) -> dict:
        result = await session.exec(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
            )
        )
        reaction = result.first()
        if not reaction:
            raise HTTPException(status_code=404, detail="Reaction not found")
        await session.delete(reaction)
        await session.commit()
        return {"message_id": message_id, "removed": True}