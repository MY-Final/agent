from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote

import aioboto3
import aiofiles
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings


class MinIOStorage:
    """MinIO 异步对象存储封装，底层使用 S3 兼容接口。"""

    def __init__(self) -> None:
        self._session: aioboto3.Session | None = None

    async def connect(self) -> None:
        self._session = aioboto3.Session()
        await self.ensure_bucket()

    async def disconnect(self) -> None:
        self._session = None

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[Any]:
        if self._session is None:
            raise RuntimeError("MinIO 客户端尚未初始化")

        async with self._session.client(
            "s3",
            endpoint_url=settings.minio_url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name=settings.minio_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=5,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        ) as client:
            # 部分 MinIO 端口代理无法正确转发 Expect: 100-continue，
            # 会导致 PUT 请求一直等待。移除该请求头后仍保持标准 S3 签名与上传行为。
            client.meta.events.register("before-send.s3.*", self._remove_expect_header)
            yield client

    @staticmethod
    def _remove_expect_header(request: Any, **_: Any) -> None:
        request.headers.pop("Expect", None)

    async def ensure_bucket(self) -> None:
        async with self._client() as client:
            try:
                await client.head_bucket(Bucket=settings.minio_bucket)
            except ClientError as exc:
                status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                error_code = exc.response.get("Error", {}).get("Code")
                if status_code != 404 and error_code not in {
                    "404",
                    "NoSuchBucket",
                    "NotFound",
                }:
                    raise
                await client.create_bucket(Bucket=settings.minio_bucket)

    async def ping(self) -> bool:
        async with self._client() as client:
            await client.head_bucket(Bucket=settings.minio_bucket)
        return True

    async def upload_fileobj(
        self,
        fileobj: BinaryIO,
        object_key: str,
        content_type: str,
        expected_size: int,
    ) -> None:
        async with self._client() as client:
            # 当前文件上限为 500MB，单次 PutObject 足够且更适合代理后的 MinIO。
            await client.put_object(
                Bucket=settings.minio_bucket,
                Key=object_key,
                Body=fileobj,
                ContentLength=expected_size,
                ContentType=content_type,
            )
            # 上传完成后通过 HEAD 校验对象，避免网络中断产生不完整记录。
            metadata = await client.head_object(
                Bucket=settings.minio_bucket,
                Key=object_key,
            )
            actual_size = int(metadata.get("ContentLength", -1))
            if actual_size != expected_size:
                try:
                    await client.delete_object(
                        Bucket=settings.minio_bucket,
                        Key=object_key,
                    )
                finally:
                    raise RuntimeError(
                        f"MinIO 对象大小校验失败，预期 {expected_size} 字节，实际 {actual_size} 字节"
                    )

    async def object_exists(self, object_key: str) -> bool:
        async with self._client() as client:
            return await self._object_exists_with_client(client, object_key)

    async def download_to_path(self, object_key: str, destination: Path) -> int:
        """将 MinIO 对象以流式方式下载到指定临时文件。"""
        destination.parent.mkdir(parents=True, exist_ok=True)
        async with self._client() as client:
            try:
                response = await client.get_object(
                    Bucket=settings.minio_bucket,
                    Key=object_key,
                )
            except ClientError as exc:
                status_code = exc.response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                error_code = exc.response.get("Error", {}).get("Code")
                if status_code == 404 or error_code in {
                    "404",
                    "NoSuchKey",
                    "NotFound",
                }:
                    raise FileNotFoundError("MinIO 中不存在该文件对象") from exc
                raise

            expected_size = int(response.get("ContentLength", -1))
            written_size = 0
            body = response["Body"]
            async with body:
                async with aiofiles.open(destination, "wb") as output:
                    while chunk := await body.read(1024 * 1024):
                        written_size += len(chunk)
                        await output.write(chunk)

        if expected_size >= 0 and written_size != expected_size:
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                f"MinIO 文件下载不完整，预期 {expected_size} 字节，实际 {written_size} 字节"
            )
        return written_size

    async def delete_object(self, object_key: str) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=settings.minio_bucket, Key=object_key)
            if await self._object_exists_with_client(client, object_key):
                raise RuntimeError(f"MinIO 对象删除后仍然存在：{object_key}")

    async def delete_objects(self, object_keys: list[str]) -> None:
        if not object_keys:
            return

        # 当前 MinIO 前置代理对 S3 DeleteObjects 批量请求支持不完整，
        # 逐个删除并通过 HEAD 复核，避免数据库已删除但对象仍残留。
        async with self._client() as client:
            for object_key in object_keys:
                await client.delete_object(
                    Bucket=settings.minio_bucket,
                    Key=object_key,
                )
                if await self._object_exists_with_client(client, object_key):
                    raise RuntimeError(f"MinIO 对象删除后仍然存在：{object_key}")

    @staticmethod
    async def _object_exists_with_client(client: Any, object_key: str) -> bool:
        try:
            await client.head_object(
                Bucket=settings.minio_bucket,
                Key=object_key,
            )
            return True
        except ClientError as exc:
            status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            error_code = exc.response.get("Error", {}).get("Code")
            if status_code == 404 or error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    async def generate_presigned_download_url(
        self,
        object_key: str,
        original_filename: str,
        expires_in: int | None = None,
    ) -> tuple[str, int]:
        expiry = expires_in or settings.minio_presigned_expiry_seconds
        expiry = max(1, min(expiry, int(timedelta(days=7).total_seconds())))
        encoded_filename = quote(original_filename, safe="")
        disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

        if not await self.object_exists(object_key):
            raise FileNotFoundError("MinIO 中不存在该文件对象")

        async with self._client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.minio_bucket,
                    "Key": object_key,
                    "ResponseContentDisposition": disposition,
                },
                ExpiresIn=expiry,
            )
        return str(url), expiry


minio_storage = MinIOStorage()
