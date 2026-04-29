import logging
from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS, MAX_PRESCRIPTION_TEXT_CHARS, MAX_UPLOAD_BYTES
from app.llm.client import ClaudeLLM, LLMError, StructuredLLM
from app.llm.extract import extract_from_file, extract_from_text
from app.pipeline import analyze
from app.schemas import AnalysisResult, AnalyzeRequest, PrescriptionExtraction

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="MedGuard API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_llm() -> StructuredLLM:
    return ClaudeLLM()


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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/prescriptions/extract", response_model=PrescriptionExtraction)
async def extract_prescription(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    llm: StructuredLLM = Depends(get_llm),
):
    text = (text or "").strip()
    if (file is None) == (not text):
        raise HTTPException(422, "Send either a prescription file or prescription text, not both.")

    try:
        if file is not None:
            data = await file.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "File is too large (max 10 MB).")
            media_type = sniff_media_type(data)
            if media_type is None:
                raise HTTPException(415, "Upload a JPEG, PNG, WebP, GIF or PDF file.")
            return await run_in_threadpool(extract_from_file, llm, data, media_type)

        if len(text) > MAX_PRESCRIPTION_TEXT_CHARS:
            raise HTTPException(413, f"Text is too long (max {MAX_PRESCRIPTION_TEXT_CHARS} characters).")
        return await run_in_threadpool(extract_from_text, llm, text)
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/analyze", response_model=AnalysisResult)
def analyze_medications(request: AnalyzeRequest, llm: StructuredLLM = Depends(get_llm)):
    # Plain def: FastAPI runs it in a worker thread, so the blocking SDK calls are fine.
    # analyze() degrades gracefully on LLM errors, so it doesn't raise LLMError.
    return analyze(llm, request)
