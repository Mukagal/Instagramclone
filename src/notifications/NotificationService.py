from typing import Optional

from fastapi import HTTPException
from sqlmodel import desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db.models import Notification, NotificationTypeEnum, User, UserProfile


class NotificationService:
    async def create_notification(
        self,
        session: AsyncSession,
        recipient_id: int,
        notification_type: NotificationTypeEnum,
        actor_id: Optional[int] = None,
        post_id: Optional[int] = None,
        reel_id: Optional[int] = None,
        story_id: Optional[int] = None,
        comment_id: Optional[int] = None,
        follow_id: Optional[int] = None,
    ) -> Optional[Notification]:
        if actor_id and actor_id == recipient_id:
            return None

        notification = Notification(
            recipient_id=recipient_id,
            actor_id=actor_id,
            notification_type=notification_type,
            post_id=post_id,
            reel_id=reel_id,
            story_id=story_id,
            comment_id=comment_id,
            follow_id=follow_id,
        )
        session.add(notification)
        await session.flush()
        return notification

    async def get_notifications(
        self,
        user_id: int,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 30,
    ) -> list[dict]:
        result = await session.exec(
            select(Notification)
            .where(Notification.recipient_id == user_id)
            .order_by(desc(Notification.created_at))
            .offset(skip)
            .limit(limit)
        )
        notifications = result.all()
        actor_ids = [n.actor_id for n in notifications if n.actor_id]
        actors = await self._get_actor_info(actor_ids, session)

        return [
            {
                "id": n.id,
                "recipient_id": n.recipient_id,
                "actor_id": n.actor_id,
                "actor": actors.get(n.actor_id) if n.actor_id else None,
                "notification_type": n.notification_type,
                "is_read": n.is_read,
                "post_id": n.post_id,
                "reel_id": n.reel_id,
                "story_id": n.story_id,
                "comment_id": n.comment_id,
                "follow_id": n.follow_id,
                "created_at": n.created_at,
            }
            for n in notifications
        ]

    async def get_unread_count(self, user_id: int, session: AsyncSession) -> int:
        result = await session.exec(
            select(func.count(Notification.id)).where(
                Notification.recipient_id == user_id,
                Notification.is_read == False,
            )
        )
        return result.one()

    async def mark_read(
        self, notification_id: int, user_id: int, session: AsyncSession
    ) -> dict:
        notification = await self._get_owned_notification(
            notification_id, user_id, session
        )
        notification.is_read = True
        await session.commit()
        return {"id": notification.id, "is_read": notification.is_read}

    async def mark_all_read(self, user_id: int, session: AsyncSession) -> dict:
        result = await session.exec(
            select(Notification).where(
                Notification.recipient_id == user_id,
                Notification.is_read == False,
            )
        )
        notifications = result.all()
        for notification in notifications:
            notification.is_read = True
        await session.commit()
        return {"updated": len(notifications)}

    async def delete_notification(
        self, notification_id: int, user_id: int, session: AsyncSession
    ) -> None:
        notification = await self._get_owned_notification(
            notification_id, user_id, session
        )
        await session.delete(notification)
        await session.commit()

    async def _get_owned_notification(
        self, notification_id: int, user_id: int, session: AsyncSession
    ) -> Notification:
        result = await session.exec(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_id == user_id,
            )
        )
        notification = result.first()
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        return notification

    async def _get_actor_info(
        self, actor_ids: list[int], session: AsyncSession
    ) -> dict[int, dict]:
        if not actor_ids:
            return {}
        result = await session.exec(
            select(User.id, User.username, User.is_blue_verified, UserProfile.avatar_path)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.id.in_(list(set(actor_ids))))
        )
        return {
            user_id: {
                "id": user_id,
                "username": username,
                "is_blue_verified": is_blue_verified,
                "avatar_path": avatar_path,
            }
            for user_id, username, is_blue_verified, avatar_path in result.all()
        }


notification_service = NotificationService()
