from __future__ import annotations

from ..errors import ProjectScanError


def _default_pdf_extractor(data: bytes) -> str:
    """Extract text from PDF bytes using pypdf (lazy import; requires the [pdf] extra)."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_text(filename: str, data: bytes, pdf_extractor=None) -> str:
    """Decode a source document's bytes to text, dispatching on file extension.

    Text/markdown are UTF-8 decoded; PDFs go through `pdf_extractor` (default: pypdf). The
    extractor is injectable so the dispatch is unit-testable without a real PDF or the [pdf] extra.
    Clause verification then runs against this extracted text, exactly as for plain text.
    """
    lower = filename.lower()
    if lower.endswith(".pdf"):
        extractor = pdf_extractor or _default_pdf_extractor
        try:
            return extractor(data)
        except ImportError as exc:
            raise ProjectScanError(
                f"reading {filename} needs the PDF extra — "
                f"`pip install 'compliance-agent[pdf]'` ({exc})"
            ) from exc
        except Exception as exc:
            raise ProjectScanError(f"cannot extract text from {filename}: {exc}") from exc
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProjectScanError(f"cannot decode {filename} as UTF-8: {exc}") from exc
