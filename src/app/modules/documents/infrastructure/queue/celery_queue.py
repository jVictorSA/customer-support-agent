import asyncio

from app.modules.documents.infrastructure.queue.celery_app import (
    celery_app,
)


class CeleryTaskQueue:
    async def enqueue_ingestion(self, document_id: int) -> None:
        await asyncio.to_thread(
            celery_app.send_task,
            "documents.ingest",
            args=[document_id],
            queue="documents.ingest",
        )
