from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator
from datetime import datetime
from typing import Optional
from ..db.models import GenderEnum

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=6)
    phone_number: Optional[str] = Field(default=None)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace(".", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, underscores and dots")
        return v.lower()


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class UserUpdate(BaseModel):
    """Fields the user can edit on their own account."""
    username: Optional[str] = Field(default=None, min_length=3, max_length=30)
    password: Optional[str] = Field(default=None, min_length=6)
    phone_number: Optional[str] = None
    is_private: Optional[bool] = None


class UserProfileUpdate(BaseModel):
    """Fields that live in UserProfile (bio, website, etc.)."""
    full_name: Optional[str] = Field(default=None, max_length=60)
    bio: Optional[str] = Field(default=None, max_length=150)
    website: Optional[str] = Field(default=None)
    gender: Optional[GenderEnum] = None
    # business / creator
    category: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None



class ProfileOut(BaseModel):
    """Embedded profile info returned inside user responses."""
    full_name: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    gender: Optional[GenderEnum] = None
    avatar_path: Optional[str] = None
    category: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0

    class Config:
        from_attributes = True


class UserPublic(BaseModel):
    """Minimal public view — safe to expose to any visitor."""
    id: int
    username: str
    is_blue_verified: bool = False
    profile: Optional[ProfileOut] = None

    class Config:
        from_attributes = True


class UserSafe(BaseModel):
    """
    Extended public view shown on profile pages.
    Hides sensitive auth fields (password, tokens, ban details).
    """
    id: int
    username: str
    is_private: bool = False
    is_business: bool = False
    is_creator: bool = False
    is_blue_verified: bool = False
    is_verified: bool = False          # email verified
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    profile: Optional[ProfileOut] = None

    class Config:
        from_attributes = True


class UserMe(BaseModel):
    """
    Full self-view — returned only to the authenticated owner.
    Includes sensitive fields the user needs to manage their account.
    """
    id: int
    username: str
    email: str
    phone_number: Optional[str] = None
    is_private: bool = False
    is_business: bool = False
    is_creator: bool = False
    is_blue_verified: bool = False
    is_verified: bool = False
    is_banned: bool = False
    ban_reason: Optional[str] = None
    is_staff: bool = False
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    profile: Optional[ProfileOut] = None

    class Config:
        from_attributes = True


class UserAdminView(UserMe):
    """Staff-only view — all fields including moderation state."""
    verification_token: Optional[str] = None
    reset_password_token: Optional[str] = None

    class Config:
        from_attributes = True



class TokenResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    user: UserPublic


class AccessTokenResponse(BaseModel):
    access_token: str