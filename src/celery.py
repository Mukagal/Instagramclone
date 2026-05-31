from celery import Celery
from .config import Config

celery = Celery(
    "messagge",
    broker=Config.REDIS_URL,
    backend=Config.REDIS_URL,
    include=["src.tasks.image_task", "src.tasks.mail_task"]
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)