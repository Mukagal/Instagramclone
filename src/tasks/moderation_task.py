import logging
import base64
import requests
import psycopg
from ..celery import celery
from ..config import Config
import cloudinary
import cloudinary.uploader
import re

logger = logging.getLogger(__name__)

def get_db_connection(db_url: str):
    clean_url = re.sub(r'\?.*$', '', db_url.replace("+asyncpg", ""))
    if "localhost" in clean_url or "172." in clean_url or "postgres:" in clean_url:
        return psycopg.connect(clean_url)
    return psycopg.connect(clean_url, sslmode='require')

@celery.task(name="moderate_image")
def moderate_image(post_id: int, image_bytes_b64: str, db_url: str):

    image_bytes = base64.b64decode(image_bytes_b64)

    response = requests.post(
        "https://api.sightengine.com/1.0/check.json",
        files={"media": ("image.jpg", image_bytes, "image/jpeg")},
        data={
            "models": "nudity,violence,offensive",
            "api_user": Config.SIGHTENGINE_API_USER,
            "api_secret": Config.SIGHTENGINE_API_SECRET,
        }
    )

    result = response.json()
    logger.info(f"[Moderation] post_id={post_id} raw result: {result}")

    if result.get("status") != "success":
        logger.error(f"[Moderation] API error for post_id={post_id}: {result}")
        return {"error": result}

    nudity_score   = result.get("nudity", {}).get("raw", 0.0)
    violence_score = result.get("violence", {}).get("prob", 0.0)
    offensive_score = result.get("offensive", {}).get("prob", 0.0)

    THRESHOLD = 0.7
    is_flagged = any([
        nudity_score   >= THRESHOLD,
        violence_score >= THRESHOLD,
        offensive_score >= THRESHOLD,
    ])

    flag_reason = (
        f"nudity={nudity_score:.2f}, "
        f"violence={violence_score:.2f}, "
        f"offensive={offensive_score:.2f}"
    )

    logger.info(
        f"[Moderation] post_id={post_id} | {flag_reason} | flagged={is_flagged}"
    )

    if is_flagged:
        conn = get_db_connection(db_url)
        cur = conn.cursor()

        cur.execute(
            "UPDATE posts SET is_flagged = TRUE, flag_reason = %s WHERE id = %s",
            (flag_reason, post_id)
        )

        cur.execute("SELECT author_id FROM posts WHERE id = %s", (post_id,))
        row = cur.fetchone()

        if row:
            author_id = row[0]
            cur.execute(
                "UPDATE users SET is_banned = TRUE, ban_reason = %s WHERE id = %s",
                (f"Posted flagged content: {flag_reason}", author_id)
            )
            logger.warning(f"[Moderation]  User {author_id} banned for post {post_id}: {flag_reason}")
            cur.execute("SELECT image_path FROM posts WHERE author_id = %s", (author_id,))
            post_images = cur.fetchall()

            cur.execute("SELECT image_path FROM stories WHERE author_id = %s", (author_id,))
            story_images = cur.fetchall()   

            cloudinary.config(
                cloud_name=Config.CLOUDINARY_CLOUD_NAME,
                api_key=Config.CLOUDINARY_API_KEY,
                api_secret=Config.CLOUDINARY_API_SECRET
            )

            for (img_url,) in post_images + story_images:
                if img_url:
                    public_id = "/".join(img_url.split("/")[-2:]).split(".")[0]
                    try:
                        cloudinary.uploader.destroy(public_id)
                    except Exception as e:
                        logger.error(f"[Moderation] Failed to delete cloudinary image {public_id}: {e}")

            cur.execute("UPDATE posts SET image_path = NULL, content = '[removed]' WHERE author_id = %s", (author_id,))
            cur.execute("UPDATE stories SET image_path = NULL WHERE author_id = %s", (author_id,))

            cur.execute("DELETE FROM user_compressed_images WHERE user_id = %s", (author_id,))

            logger.info(f"[Moderation] Cleared media for banned user {author_id}")         

        conn.commit()
        cur.close()
        conn.close()

    return {
        "post_id": post_id,
        "nudity": nudity_score,
        "violence": violence_score,
        "offensive": offensive_score,
        "is_flagged": is_flagged
    }

@celery.task(name="moderate_profile_image")
def moderate_profile_image(user_id: int, image_bytes_b64: str, db_url: str):

    image_bytes = base64.b64decode(image_bytes_b64)
    response = requests.post(
        "https://api.sightengine.com/1.0/check.json",
        files={"media": ("image.jpg", image_bytes, "image/jpeg")},
        data={
            "models": "nudity,violence,offensive",
            "api_user": Config.SIGHTENGINE_API_USER,
            "api_secret": Config.SIGHTENGINE_API_SECRET,
        }
    )
    result = response.json()
    if result.get("status") != "success":
        logger.error(f"[Moderation] Profile image API error user_id={user_id}: {result}")
        return

    nudity_score    = result.get("nudity", {}).get("raw", 0.0)
    violence_score  = result.get("violence", {}).get("prob", 0.0)
    offensive_score = result.get("offensive", {}).get("prob", 0.0)

    THRESHOLD = 0.7
    is_flagged = any([nudity_score >= THRESHOLD, violence_score >= THRESHOLD, offensive_score >= THRESHOLD])
    flag_reason = f"nudity={nudity_score:.2f}, violence={violence_score:.2f}, offensive={offensive_score:.2f}"

    logger.info(f"[Moderation] Profile user_id={user_id} | {flag_reason} | flagged={is_flagged}")

    if is_flagged:
        conn = get_db_connection(db_url)
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET profile_image_path = NULL, is_banned = TRUE, ban_reason = %s WHERE id = %s",
            (f"Inappropriate profile image: {flag_reason}", user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.warning(f"[Moderation] User {user_id} banned for inappropriate profile image: {flag_reason}")


    return {
        "user_id": user_id,
        "nudity": nudity_score,
        "violence": violence_score,
        "offensive": offensive_score,
        "is_flagged": is_flagged,
    }