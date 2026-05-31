import secrets
import logging
import math
from typing import Optional

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from ..tasks.mail_task import send_confirmation_email
from ..config import Config
from ..db.models import (
    User,
    UserProfile,
    UserAvatar,
    Follow,
    Block,
    FollowStatusEnum,
    NotificationTypeEnum,
)
from ..notifications.NotificationService import notification_service
from ..users.utils import generate_password_hash
from .UserSchemas import UserCreate, UserUpdate, UserProfileUpdate

cloudinary.config(
    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
    api_key=Config.CLOUDINARY_API_KEY,
    api_secret=Config.CLOUDINARY_API_SECRET,
)

log = logging.getLogger(__name__)


class UserService:


    async def _get_user_with_profile(self, statement, session: AsyncSession) -> Optional[User]:
        """Execute a select statement and eagerly load the nested profile."""
        statement = statement.options(selectinload(User.profile))
        result = await session.exec(statement)
        return result.first()


    async def get_user(self, user_id: int, session: AsyncSession) -> Optional[User]:
        return await self._get_user_with_profile(
            select(User).where(User.id == user_id), session
        )

    async def get_user_by_email(self, email: str, session: AsyncSession) -> Optional[User]:
        return await self._get_user_with_profile(
            select(User).where(User.email == email), session
        )

    async def get_user_by_username(self, username: str, session: AsyncSession) -> Optional[User]:
        return await self._get_user_with_profile(
            select(User).where(User.username == username), session
        )

    async def user_exists(self, email: str, session: AsyncSession) -> bool:
        user = await self.get_user_by_email(email, session)
        return user is not None

    async def get_all_users(
        self,
        session: AsyncSession,
        username: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ):
        statement = (
            select(User)
            .where(User.is_banned == False)
            .options(selectinload(User.profile))
            .offset(skip)
            .limit(limit)
        )
        if username:
            statement = statement.where(User.username.ilike(f"%{username}%"))
        result = await session.exec(statement)
        return result.all()


    async def create_user(self, user_data: UserCreate, session: AsyncSession) -> User:
        if await self.user_exists(user_data.email, session):
            raise HTTPException(status_code=409, detail="Email already registered")

        existing_username = await self.get_user_by_username(user_data.username, session)
        if existing_username:
            raise HTTPException(status_code=409, detail="Username already taken")

        token = secrets.token_urlsafe(32)

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            phone_number=user_data.phone_number,
            password_hash=generate_password_hash(user_data.password),
            verification_token=token,
            is_verified=False,
        )
        session.add(new_user)
        await session.flush()  

        profile = UserProfile(user_id=new_user.id)
        session.add(profile)

        await session.commit()
        await session.refresh(new_user)

        
        send_confirmation_email.delay(new_user.email, new_user.username, token)

        return await self.get_user(new_user.id, session)


    async def update_user(
        self, user_id: int, update_data: UserUpdate, session: AsyncSession
    ) -> Optional[User]:
        user = await self.get_user(user_id, session)
        if not user:
            return None

        data = update_data.model_dump(exclude_unset=True)

        if "username" in data:
            existing = await self.get_user_by_username(data["username"], session)
            if existing and existing.id != user_id:
                raise HTTPException(status_code=409, detail="Username already taken")

        if "password" in data:
            data["password_hash"] = generate_password_hash(data.pop("password"))

        for k, v in data.items():
            setattr(user, k, v)

        await session.commit()
        await session.refresh(user)
        return await self.get_user(user_id, session)

    async def update_profile(
        self, user_id: int, update_data: UserProfileUpdate, session: AsyncSession
    ) -> Optional[User]:
        """Update the UserProfile row linked to this user."""
        user = await self.get_user(user_id, session)
        if not user:
            return None

        if not user.profile:
            profile = UserProfile(user_id=user_id)
            session.add(profile)
            await session.flush()
            await session.refresh(user)

        for k, v in update_data.model_dump(exclude_unset=True).items():
            setattr(user.profile, k, v)

        await session.commit()
        return await self.get_user(user_id, session)



    async def delete_user(self, user_id: int, session: AsyncSession) -> bool:
        user = await self.get_user(user_id, session)
        if not user:
            return False
        await session.delete(user)
        await session.commit()
        return True


    async def upload_avatar(
        self, user_id: int, file: UploadFile, session: AsyncSession
    ) -> Optional[User]:
        user = await self.get_user(user_id, session)
        if not user:
            return None

        result = cloudinary.uploader.upload(
            file.file,
            folder="avatars",
            public_id=f"user_{user_id}",
            overwrite=True,
            transformation=[
                {"width": 300, "height": 300, "crop": "fill", "gravity": "face"}
            ],
        )
        secure_url = result["secure_url"]

        if not user.profile:
            user.profile = UserProfile(user_id=user_id)
            session.add(user.profile)
            await session.flush()

        user.profile.avatar_path = secure_url
        await session.commit()
        return await self.get_user(user_id, session)


    async def follow_user(
        self, follower_id: int, target_id: int, session: AsyncSession
    ) -> dict:
        if follower_id == target_id:
            raise HTTPException(status_code=400, detail="You cannot follow yourself")

        blocked = await session.exec(
            select(Block).where(
                (
                    (Block.blocker_id == follower_id) & (Block.blocked_id == target_id)
                ) | (
                    (Block.blocker_id == target_id) & (Block.blocked_id == follower_id)
                )
            )
        )
        if blocked.first():
            raise HTTPException(status_code=403, detail="Action not allowed")

        existing = await session.exec(
            select(Follow).where(
                Follow.follower_id == follower_id, Follow.followed_id == target_id
            )
        )
        if existing.first():
            raise HTTPException(status_code=409, detail="Already following")

        target = await self.get_user(target_id, session)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        status = (
            FollowStatusEnum.PENDING if target.is_private else FollowStatusEnum.ACCEPTED
        )
        follow = Follow(follower_id=follower_id, followed_id=target_id, status=status)
        session.add(follow)
        await session.flush()

        if status == FollowStatusEnum.ACCEPTED:
            await self._increment_follow_counts(follower_id, target_id, session)

        await notification_service.create_notification(
            session,
            recipient_id=target_id,
            actor_id=follower_id,
            notification_type=(
                NotificationTypeEnum.FOLLOW
                if status == FollowStatusEnum.ACCEPTED
                else NotificationTypeEnum.FOLLOW_REQUEST
            ),
            follow_id=follow.id,
        )

        await session.commit()
        return {"status": status.value}

    async def unfollow_user(
        self, follower_id: int, target_id: int, session: AsyncSession
    ) -> bool:
        result = await session.exec(
            select(Follow).where(
                Follow.follower_id == follower_id, Follow.followed_id == target_id
            )
        )
        follow = result.first()
        if not follow:
            raise HTTPException(status_code=404, detail="Not following this user")

        was_accepted = follow.status == FollowStatusEnum.ACCEPTED
        await session.delete(follow)

        if was_accepted:
            await self._decrement_follow_counts(follower_id, target_id, session)

        await session.commit()
        return True

    async def accept_follow_request(
        self, owner_id: int, requester_id: int, session: AsyncSession
    ) -> bool:
        result = await session.exec(
            select(Follow).where(
                Follow.follower_id == requester_id,
                Follow.followed_id == owner_id,
                Follow.status == FollowStatusEnum.PENDING,
            )
        )
        follow = result.first()
        if not follow:
            raise HTTPException(status_code=404, detail="Follow request not found")

        follow.status = FollowStatusEnum.ACCEPTED
        await self._increment_follow_counts(requester_id, owner_id, session)
        await notification_service.create_notification(
            session,
            recipient_id=requester_id,
            actor_id=owner_id,
            notification_type=NotificationTypeEnum.FOLLOW_ACCEPTED,
            follow_id=follow.id,
        )
        await session.commit()
        return True

    async def reject_follow_request(
        self, owner_id: int, requester_id: int, session: AsyncSession
    ) -> bool:
        result = await session.exec(
            select(Follow).where(
                Follow.follower_id == requester_id,
                Follow.followed_id == owner_id,
                Follow.status == FollowStatusEnum.PENDING,
            )
        )
        follow = result.first()
        if not follow:
            raise HTTPException(status_code=404, detail="Follow request not found")
        await session.delete(follow)
        await session.commit()
        return True

    async def remove_follower(
        self, owner_id: int, follower_id: int, session: AsyncSession
    ) -> bool:
        """Owner removes someone who follows them."""
        result = await session.exec(
            select(Follow).where(
                Follow.follower_id == follower_id,
                Follow.followed_id == owner_id,
                Follow.status == FollowStatusEnum.ACCEPTED,
            )
        )
        follow = result.first()
        if not follow:
            raise HTTPException(status_code=404, detail="Follower not found")
        await session.delete(follow)
        await self._decrement_follow_counts(follower_id, owner_id, session)
        await session.commit()
        return True

    async def get_followers(
        self, user_id: int, session: AsyncSession, skip: int = 0, limit: int = 20
    ):
        result = await session.exec(
            select(User)
            .join(Follow, Follow.follower_id == User.id)
            .where(
                Follow.followed_id == user_id,
                Follow.status == FollowStatusEnum.ACCEPTED,
            )
            .options(selectinload(User.profile))
            .offset(skip)
            .limit(limit)
        )
        return result.all()

    async def get_following(
        self, user_id: int, session: AsyncSession, skip: int = 0, limit: int = 20
    ):
        result = await session.exec(
            select(User)
            .join(Follow, Follow.followed_id == User.id)
            .where(
                Follow.follower_id == user_id,
                Follow.status == FollowStatusEnum.ACCEPTED,
            )
            .options(selectinload(User.profile))
            .offset(skip)
            .limit(limit)
        )
        return result.all()

    async def get_pending_follow_requests(
        self, user_id: int, session: AsyncSession
    ):
        """Incoming pending follow requests for a private account."""
        result = await session.exec(
            select(User)
            .join(Follow, Follow.follower_id == User.id)
            .where(
                Follow.followed_id == user_id,
                Follow.status == FollowStatusEnum.PENDING,
            )
            .options(selectinload(User.profile))
        )
        return result.all()

    async def block_user(
        self, blocker_id: int, target_id: int, session: AsyncSession
    ) -> bool:
        if blocker_id == target_id:
            raise HTTPException(status_code=400, detail="You cannot block yourself")

        existing = await session.exec(
            select(Block).where(
                Block.blocker_id == blocker_id, Block.blocked_id == target_id
            )
        )
        if existing.first():
            raise HTTPException(status_code=409, detail="Already blocked")

        await session.exec(
            delete(Follow).where(
                ((Follow.follower_id == blocker_id) & (Follow.followed_id == target_id))
                | ((Follow.follower_id == target_id) & (Follow.followed_id == blocker_id))
            )
        )

        block = Block(blocker_id=blocker_id, blocked_id=target_id)
        session.add(block)
        await session.commit()
        return True

    async def unblock_user(
        self, blocker_id: int, target_id: int, session: AsyncSession
    ) -> bool:
        result = await session.exec(
            select(Block).where(
                Block.blocker_id == blocker_id, Block.blocked_id == target_id
            )
        )
        block = result.first()
        if not block:
            raise HTTPException(status_code=404, detail="Block not found")
        await session.delete(block)
        await session.commit()
        return True

    async def get_blocked_users(self, user_id: int, session: AsyncSession):
        result = await session.exec(
            select(User)
            .join(Block, Block.blocked_id == User.id)
            .where(Block.blocker_id == user_id)
            .options(selectinload(User.profile))
        )
        return result.all()


    async def ban_user(
        self, user_id: int, reason: str, session: AsyncSession
    ) -> Optional[User]:
        user = await self.get_user(user_id, session)
        if not user:
            return None
        user.is_banned = True
        user.ban_reason = reason
        await session.commit()
        return await self.get_user(user_id, session)

    async def unban_user(self, user_id: int, session: AsyncSession) -> Optional[User]:
        user = await self.get_user(user_id, session)
        if not user:
            return None
        user.is_banned = False
        user.ban_reason = None
        await session.commit()
        return await self.get_user(user_id, session)



    async def _increment_follow_counts(
        self, follower_id: int, followed_id: int, session: AsyncSession
    ):
        follower_profile = await session.exec(
            select(UserProfile).where(UserProfile.user_id == follower_id)
        )
        fp = follower_profile.first()
        if fp:
            fp.following_count += 1

        followed_profile = await session.exec(
            select(UserProfile).where(UserProfile.user_id == followed_id)
        )
        fdp = followed_profile.first()
        if fdp:
            fdp.follower_count += 1

    async def _decrement_follow_counts(
        self, follower_id: int, followed_id: int, session: AsyncSession
    ):
        follower_profile = await session.exec(
            select(UserProfile).where(UserProfile.user_id == follower_id)
        )
        fp = follower_profile.first()
        if fp:
            fp.following_count = max(0, fp.following_count - 1)

        followed_profile = await session.exec(
            select(UserProfile).where(UserProfile.user_id == followed_id)
        )
        fdp = followed_profile.first()
        if fdp:
            fdp.follower_count = max(0, fdp.follower_count - 1)
