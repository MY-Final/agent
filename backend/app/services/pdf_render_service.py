import tempfile
from pathlib import Path

import fitz

from app.core.exceptions import AppException
from app.core.minio import MinIOStorage


class PdfRenderService:
    """用 PyMuPDF 把 MinIO 里的 PDF 按页渲染成 PNG，供人工对照原文。"""

    @staticmethod
    async def page_count(storage: MinIOStorage, object_key: str) -> int:
        with tempfile.TemporaryDirectory(prefix="pdf_info_") as temp_dir:
            local_path = Path(temp_dir) / "document.pdf"
            await storage.download_to_path(object_key, local_path)
            with fitz.open(local_path) as document:
                return document.page_count

    @staticmethod
    async def render_page(
        storage: MinIOStorage,
        object_key: str,
        page_number: int,
        *,
        dpi: int = 130,
    ) -> bytes:
        with tempfile.TemporaryDirectory(prefix="pdf_render_") as temp_dir:
            local_path = Path(temp_dir) / "document.pdf"
            await storage.download_to_path(object_key, local_path)
            with fitz.open(local_path) as document:
                if page_number < 1 or page_number > document.page_count:
                    raise AppException(
                        f"页码超出范围（1-{document.page_count}）",
                        code=40023,
                        status_code=400,
                    )
                page = document.load_page(page_number - 1)
                pixmap = page.get_pixmap(dpi=dpi)
                return pixmap.tobytes("png")
