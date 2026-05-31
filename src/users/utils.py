import logging
from datetime import datetime, timedelta
import bcrypt
import jwt
from ..config import Config
import uuid
import redis.asyncio as aioredis


def generate_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hash.encode("utf-8"))


def create_access_token(
    user_data: dict, expiry: timedelta = None, refresh: bool = False
) -> str:
    payload = {
        "user": user_data,
        "exp": datetime.now() + (expiry if expiry is not None else timedelta(minutes=60)),
        "jti": str(uuid.uuid4()),
        "refresh": refresh,
    }
    return jwt.encode(payload=payload, key=Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(jwt=token, key=Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
    except jwt.PyJWTError as e:
        logging.exception(e)
        return None
    except Exception as e:
        logging.exception(e)
        return None


token_blocklist = aioredis.from_url(
    Config.REDIS_URL, encoding="utf-8", decode_responses=True
)


async def add_jti_to_blocklist(jti: str) -> None:
    """Block a token by its jti. TTL matches access token lifetime (1 hour)."""
    await token_blocklist.set(name=jti, value="blocked", ex=3600)


async def is_jti_blocked(jti: str) -> bool:
    return await token_blocklist.exists(jti) > 0