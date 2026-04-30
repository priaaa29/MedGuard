from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.deps import current_user, enforce_limit, get_llm
from app.config import EXTRACTIONS_PER_HOUR, MAX_PRESCRIPTION_TEXT_CHARS, MAX_UPLOAD_BYTES
from app.llm.client import LLMError, StructuredLLM
from app.llm.extract import extract_from_file, extract_from_text
from app.models import User
from app.schemas import PrescriptionExtraction

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])


def sniff_media_type(data: bytes) -> str | None:
    """Identify the file from its bytes; never trust the client's Content-Type."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.post("/extract", response_model=PrescriptionExtraction)
async def extract_prescription(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    user: User = Depends(current_user),
    llm: StructuredLLM = Depends(get_llm),
):
    """Read a prescription. The file is processed in memory and never stored."""
    text = (text or "").strip()
    if (file is None) == (not text):
        raise HTTPException(422, "Send either a prescription file or prescription text, not both.")

    if file is not None:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "File is too large (max 10 MB).")
        media_type = sniff_media_type(data)
        if media_type is None:
            raise HTTPException(415, "Upload a JPEG, PNG, WebP, GIF or PDF file.")
    elif len(text) > MAX_PRESCRIPTION_TEXT_CHARS:
        raise HTTPException(413, f"Text is too long (max {MAX_PRESCRIPTION_TEXT_CHARS} characters).")

    enforce_limit(
        f"extract:{user.id}", EXTRACTIONS_PER_HOUR, 3600,
        "You've read a lot of prescriptions this hour. Please try again later.",
    )
    try:
        if file is not None:
            return await run_in_threadpool(extract_from_file, llm, data, media_type)
        return await run_in_threadpool(extract_from_text, llm, text)
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
