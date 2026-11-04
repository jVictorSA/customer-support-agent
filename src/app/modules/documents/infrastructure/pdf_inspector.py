from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.modules.documents.application.exceptions import (
    DocumentUnprocessableError,
    DocumentUnsupportedMediaTypeError,
)


class PypdfInspector:
    def inspect(self, path: Path) -> int:
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise DocumentUnsupportedMediaTypeError()
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                raise DocumentUnprocessableError("Encrypted PDFs are not supported")
            return len(reader.pages)
        except DocumentUnprocessableError:
            raise
        except (PdfReadError, ValueError, OSError) as exc:
            raise DocumentUnprocessableError("Malformed PDF") from exc
