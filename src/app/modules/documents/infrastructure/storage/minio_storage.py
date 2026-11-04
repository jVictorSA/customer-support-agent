import asyncio
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.modules.documents.application.exceptions import (
    DocumentStorageUnavailableError,
)


class MinioDocumentStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> None:
        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket
        self._bucket_ready = False

    async def put_pdf(
        self, *, checksum: str, path: Path, content_type: str
    ) -> str:
        key = f"sources/{checksum}.pdf"

        def upload() -> None:
            self._ensure_bucket()
            self._client.fput_object(
                self._bucket,
                key,
                str(path),
                content_type=content_type,
            )

        try:
            await asyncio.to_thread(upload)
        except Exception as exc:
            raise DocumentStorageUnavailableError() from exc
        return key

    async def download_pdf(
        self, *, checksum: str, destination: Path
    ) -> None:
        key = f"sources/{checksum}.pdf"

        def download() -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            self._client.fget_object(self._bucket, key, str(destination))

        try:
            await asyncio.to_thread(download)
        except Exception as exc:
            raise DocumentStorageUnavailableError() from exc

    async def put_checkpoint(self, *, key: str, data: bytes) -> None:
        from io import BytesIO

        def upload() -> None:
            self._ensure_bucket()
            self._client.put_object(
                self._bucket,
                key,
                BytesIO(data),
                length=len(data),
                content_type="application/octet-stream",
            )

        try:
            await asyncio.to_thread(upload)
        except Exception as exc:
            raise DocumentStorageUnavailableError() from exc

    async def get_checkpoint(self, *, key: str) -> bytes | None:
        def download() -> bytes | None:
            response = None
            try:
                response = self._client.get_object(self._bucket, key)
                return response.read()
            except S3Error as exc:
                if exc.code in {"NoSuchKey", "NoSuchBucket"}:
                    return None
                raise
            finally:
                if response is not None:
                    response.close()
                    response.release_conn()

        try:
            return await asyncio.to_thread(download)
        except Exception as exc:
            raise DocumentStorageUnavailableError() from exc

    async def list_checkpoints(self, *, prefix: str) -> list[str]:
        def list_keys() -> list[str]:
            self._ensure_bucket()
            return [
                item.object_name
                for item in self._client.list_objects(
                    self._bucket, prefix=prefix, recursive=True
                )
                if item.object_name
            ]

        try:
            return await asyncio.to_thread(list_keys)
        except Exception as exc:
            raise DocumentStorageUnavailableError() from exc

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
        self._bucket_ready = True
