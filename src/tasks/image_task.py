import io
import base64
import logging
from PIL import Image
from ..celery import celery
import psycopg
import re

logger = logging.getLogger(__name__)

def get_db_connection(db_url: str):
    clean_url = re.sub(r'\?.*$', '', db_url.replace("+asyncpg", ""))
    if "localhost" in clean_url or "172." in clean_url or "postgres:" in clean_url:
        return psycopg.connect(clean_url)
    return psycopg.connect(clean_url, sslmode='require')

@celery.task(name="compress_and_store_image")
def compress_and_store_image(user_id: int, image_bytes_b64: str, db_url: str):
    

    image_bytes = base64.b64decode(image_bytes_b64)
    original_size = len(image_bytes)

    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=60, optimize=True)
    compressed_bytes = output.getvalue()
    compressed_size = len(compressed_bytes)

    logger.info(
        f"[Image Compression] user_id={user_id} | "
        f"before={original_size / 1024:.1f}KB | "
        f"after={compressed_size / 1024:.1f}KB | "
        f"saved={((original_size - compressed_size) / original_size * 100):.1f}%"
    )

    conn = get_db_connection(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO user_compressed_images (user_id, image_data, original_size, compressed_size)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET image_data = EXCLUDED.image_data,
            original_size = EXCLUDED.original_size,
            compressed_size = EXCLUDED.compressed_size
        """,
        (user_id, psycopg.Binary(compressed_bytes), original_size, compressed_size)
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"user_id": user_id, "original_kb": original_size // 1024, "compressed_kb": compressed_size // 1024}