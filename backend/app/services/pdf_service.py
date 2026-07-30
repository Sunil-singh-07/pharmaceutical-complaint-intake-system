"""PDF text extraction service (Phase 2).

Extracts raw text from uploaded PDF files using PyMuPDF (``fitz``). This
service is purely mechanical: it validates that the uploaded bytes are a
readable, non-empty PDF and returns the concatenated text of all pages.

No business logic lives here. The extracted text is handed back to the
caller (the Complaints API) to be combined with the user's message and
passed into the existing LangGraph workflow, per 04_CODING_CONTRACT.md
section 5.
"""

import logging

import fitz  # PyMuPDF

from app.services.exceptions import (
    PDFCorruptedError,
    PDFEmptyError,
    PDFInvalidFileTypeError,
)

logger = logging.getLogger(__name__)

#: PDF file signature ("magic bytes") that a valid PDF must start with.
_PDF_MAGIC = b"%PDF-"


def _validate_pdf_bytes(file_bytes: bytes, filename: str | None) -> None:
    """Validate that the given bytes look like a PDF file.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename: Original filename of the upload, if any, used only for
            error messages.

    Raises:
        PDFInvalidFileTypeError: If ``file_bytes`` is empty or does not
            start with the PDF file signature.
    """
    if not file_bytes:
        raise PDFInvalidFileTypeError(filename or "<unknown>")

    if not file_bytes.startswith(_PDF_MAGIC):
        raise PDFInvalidFileTypeError(filename or "<unknown>")


def extract_text_from_pdf(file_bytes: bytes, filename: str | None = None) -> str:
    """Extract all text from an uploaded PDF file.

    Args:
        file_bytes: Raw bytes of the uploaded PDF file.
        filename: Original filename of the upload, if any, used only for
            error messages.

    Returns:
        The concatenated text of every page in the PDF, in page order.

    Raises:
        PDFInvalidFileTypeError: If the uploaded bytes are not a PDF
            file.
        PDFCorruptedError: If the file cannot be opened or read as a
            PDF.
        PDFEmptyError: If the PDF contains no extractable text.
    """
    _validate_pdf_bytes(file_bytes, filename)

    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - any fitz failure means corrupt
        raise PDFCorruptedError(filename or "<unknown>", str(exc)) from exc

    try:
        page_texts = [page.get_text() for page in document]
    except Exception as exc:  # noqa: BLE001 - any fitz failure means corrupt
        raise PDFCorruptedError(filename or "<unknown>", str(exc)) from exc
    finally:
        document.close()

    extracted_text = "\n".join(page_texts).strip()

    if not extracted_text:
        raise PDFEmptyError(filename or "<unknown>")

    logger.info(
        "Extracted %d characters of text from PDF '%s'.",
        len(extracted_text),
        filename or "<unknown>",
    )

    return extracted_text
