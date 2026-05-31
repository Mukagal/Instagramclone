from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

class InvalidTokenError(AppException):
    def __init__(self):
        super().__init__(401, "Invalid or expired token")

class UserNotFoundError(AppException):
    def __init__(self):
        super().__init__(404, "User not found")

class UserAlreadyExistsError(AppException):
    def __init__(self):
        super().__init__(409, "User with this email already exists")

class InvalidCredentialsError(AppException):
    def __init__(self):
        super().__init__(403, "Invalid email or password")

class TokenBlocklistedError(AppException):
    def __init__(self):
        super().__init__(401, "Token has been revoked. Please log in again")

class ConversationNotFoundError(AppException):
    def __init__(self):
        super().__init__(404, "Conversation not found")

class SelfConversationError(AppException):
    def __init__(self):
        super().__init__(400, "Cannot start a conversation with yourself")

class SenderNotInConversationError(AppException):
    def __init__(self):
        super().__init__(403, "You are not a participant in this conversation")

class MessageNotFoundError(AppException):
    def __init__(self):
        super().__init__(404, "Message not found")

class MessageOwnershipError(AppException):
    def __init__(self):
        super().__init__(403, "You can only edit or delete your own messages")

class PostNotFoundError(AppException):
    def __init__(self):
        super().__init__(404, "Post not found")

class PostOwnershipError(AppException):
    def __init__(self):
        super().__init__(403, "You can only delete your own posts")

class CommentNotFoundError(AppException):
    def __init__(self):
        super().__init__(404, "Comment not found")

class CommentOwnershipError(AppException):
    def __init__(self):
        super().__init__(403, "You can only delete your own comments")

class StoryNotFoundError(AppException):
    def __init__(self):
        super().__init__(404, "Story not found")

class StoryExpiredError(AppException):
    def __init__(self):
        super().__init__(410, "This story has expired")

class StoryOwnershipError(AppException):
    def __init__(self):
        super().__init__(403, "You can only delete your own stories")

class GroupNotFoundError(AppException):
    def __init__(self):
        super().__init__(404, "Group not found")

class NotGroupMemberError(AppException):
    def __init__(self):
        super().__init__(403, "You are not a member of this group")

class AlreadyGroupMemberError(AppException):
    def __init__(self):
        super().__init__(409, "User is already a member of this group")

class GroupAdminOnlyError(AppException):
    def __init__(self):
        super().__init__(403, "Only the group creator can perform this action")



async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "message": exc.detail}
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": e["loc"][-1], "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": True, "message": "Validation failed", "details": errors}
    )

async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "Internal server error"}
    )