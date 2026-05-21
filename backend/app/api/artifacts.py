from __future__ import annotations

import json
import re
import secrets
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from PIL import Image
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Artifact, Comment, ProcessingJob, ShareLink
from app.schemas import (
    ArtifactOut,
    CommentCreate,
    CommentOut,
    DocumentSummaryOut,
    FeedbackSummaryOut,
    MetricsOut,
    ProcessingJobOut,
    ShareLinkCreate,
    ShareLinkOut,
)
from app.services.queue import enqueue_artifact_processing, recover_stale_jobs
from app.services.feedback import generate_feedback_summary
from app.services.storage import StorageError, get_object_response, iter_streaming_body, make_api_file_url, upload_fileobj

router = APIRouter()
settings = get_settings()

ALLOWED_TYPES = {"image", "pdf"}
ALLOWED_STATUSES = {"processing", "ready", "failed", "archived"}
ALLOWED_SORTS = {"newest", "oldest", "title_az", "title_za", "most_comments", "least_comments", "recently_updated", "recently_processed", "status", "type"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
TAG_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$")
MAX_TITLE_PREFIX_CHARS = 80
MAX_GENERATED_TITLE_CHARS = 220
MAX_ARTIFACT_ID_CHARS = 80
MAX_ARTIFACT_ID_SLUG_CHARS = 58


def truncate_text(value: str, max_chars: int) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def slugify(value: str, max_chars: int = 80) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return (value.strip("-")[:max_chars].strip("-") or "artifact")


def build_artifact_title(title_prefix: str, filename: str, multiple: bool) -> str:
    file_stem = Path(filename or "artifact").stem or "artifact"
    clean_prefix = truncate_text(title_prefix, MAX_TITLE_PREFIX_CHARS)
    if clean_prefix and multiple:
        title = f"{clean_prefix} — {file_stem}"
    else:
        title = clean_prefix or file_stem or "Untitled artifact"
    return truncate_text(title, MAX_GENERATED_TITLE_CHARS)


def build_artifact_id(title: str) -> str:
    suffix = uuid4().hex[:8]
    slug = slugify(title, MAX_ARTIFACT_ID_SLUG_CHARS)
    artifact_id = f"{slug}-{suffix}"
    if len(artifact_id) > MAX_ARTIFACT_ID_CHARS:
        artifact_id = f"{slug[: MAX_ARTIFACT_ID_CHARS - len(suffix) - 1].rstrip('-')}-{suffix}"
    return artifact_id


def safe_ascii_filename(value: str | None, fallback: str = "artifact") -> str:
    """Return a header-safe ASCII filename fallback.

    Starlette encodes response headers as latin-1. Some uploaded screenshots
    contain Unicode spaces, smart punctuation, or emoji. For preview routes, the
    safest behavior is to keep Content-Disposition entirely ASCII-only.
    """

    raw_name = Path(value or fallback).name or fallback
    ascii_name = unicodedata.normalize("NFKD", raw_name).encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._-")
    return ascii_name or fallback


def content_disposition_inline(filename: str | None) -> str:
    # Keep this header 100% ASCII. Do not include filename*= here because a
    # preview route does not need a perfect download filename, and avoiding all
    # Unicode removes the latin-1 crash class completely.
    return f'inline; filename="{safe_ascii_filename(filename)}"'


def latin1_headers(headers: dict[str, str]) -> dict[str, str]:
    """Last-line guard: prevent any header value from crashing Starlette.

    If future code accidentally adds Unicode to a header, this replaces it with
    a safe ASCII approximation instead of returning a 500.
    """

    safe: dict[str, str] = {}
    for key, value in headers.items():
        safe_key = key.encode("ascii", "ignore").decode("ascii")
        safe_value = unicodedata.normalize("NFKD", str(value)).encode("latin-1", "ignore").decode("latin-1")
        safe[safe_key] = safe_value
    return safe

def parse_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []
    raw_tags = raw_tags.strip()
    try:
        parsed = json.loads(raw_tags)
        if isinstance(parsed, list):
            items = [str(tag).strip().lower() for tag in parsed if str(tag).strip()]
        else:
            items = []
    except json.JSONDecodeError:
        items = [tag.strip().lower() for tag in raw_tags.split(",") if tag.strip()]

    deduped = list(dict.fromkeys(items))
    if len(deduped) > 12:
        raise HTTPException(status_code=400, detail="Use 12 tags or fewer")
    invalid = [tag for tag in deduped if not TAG_PATTERN.match(tag)]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid tag: {invalid[0]}")
    return deduped


def detect_artifact_type(path: Path, filename: str, content_type: str | None) -> str:
    extension = Path(filename or "").suffix.lower()
    content_type = (content_type or "").lower()

    if extension in ALLOWED_PDF_EXTENSIONS or content_type == "application/pdf":
        with path.open("rb") as handle:
            if handle.read(4) != b"%PDF":
                raise HTTPException(status_code=400, detail=f"{filename} does not look like a valid PDF")
        return "pdf"

    if extension in ALLOWED_IMAGE_EXTENSIONS or content_type.startswith("image/"):
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported image extension for {filename}")
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception:
            raise HTTPException(status_code=400, detail=f"{filename} does not look like a valid image")
        return "image"

    raise HTTPException(status_code=400, detail=f"Unsupported file type for {filename}. Upload images or PDFs only.")


async def save_upload_to_temp(file: UploadFile) -> tuple[Path, int]:
    suffix = Path(file.filename or "upload.bin").suffix.lower()[:20]
    temp = tempfile.NamedTemporaryFile(prefix="artifact-upload-", suffix=suffix, delete=False)
    temp_path = Path(temp.name)
    total = 0
    try:
        while True:
            chunk = await file.read(settings.upload_chunk_bytes)
            if not chunk:
                break
            total += len(chunk)
            if total > settings.max_upload_bytes:
                raise HTTPException(status_code=413, detail=f"{file.filename or 'file'} exceeds the 10 MB upload limit")
            temp.write(chunk)
        temp.flush()
        return temp_path, total
    finally:
        temp.close()
        await file.close()


def artifact_to_out(db: Session, artifact: Artifact) -> ArtifactOut:
    comment_count = db.scalar(select(func.count(Comment.id)).where(Comment.artifact_id == artifact.id)) or 0
    feedback_summary = artifact.feedback_summary
    if comment_count and not feedback_summary:
        comments = db.scalars(
            select(Comment).where(Comment.artifact_id == artifact.id).order_by(Comment.created_at.asc())
        ).all()
        feedback_summary = generate_feedback_summary(artifact, list(comments))
    file_url = make_api_file_url(artifact.id)
    return ArtifactOut(
        id=artifact.id,
        title=artifact.title,
        description=artifact.description,
        type=artifact.type,  # type: ignore[arg-type]
        tags=artifact.tags or [],
        category=artifact.category,
        owner_name=artifact.owner_name,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
        processed_at=artifact.processed_at,
        status=artifact.status,  # type: ignore[arg-type]
        comment_count=comment_count,
        artifact_url=file_url,
        thumbnail_url=file_url if artifact.type == "image" else None,
        document_summary=artifact.document_summary,
        feedback_summary=feedback_summary,
        page_summaries=artifact.page_summaries or [],
        processing_error=artifact.processing_error,
        rating=artifact.rating,
    )


async def create_one_artifact(
    *,
    db: Session,
    file: UploadFile,
    title: str,
    description: str,
    category: str,
    owner_name: str,
    tags: list[str],
    multiple: bool,
) -> Artifact:
    if len(title.strip()) > MAX_TITLE_PREFIX_CHARS:
        raise HTTPException(status_code=400, detail=f"Title prefix must be {MAX_TITLE_PREFIX_CHARS} characters or fewer")

    temp_path, file_size = await save_upload_to_temp(file)
    if file_size == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"{file.filename or 'file'} is empty")

    try:
        artifact_type = detect_artifact_type(temp_path, file.filename or "artifact", file.content_type)
        final_title = build_artifact_title(title.strip(), file.filename or "artifact", multiple)
        artifact_id = build_artifact_id(final_title)
        suffix = Path(file.filename or "artifact.bin").suffix.lower()[:20]
        object_key = f"artifacts/{artifact_id}{suffix}"

        try:
            with temp_path.open("rb") as buffer:
                upload_fileobj(object_key, buffer, file.content_type or "application/octet-stream")
        except StorageError as exc:
            # The raw file could not be persisted, so do not enqueue a job.
            # Return a clear error to the Publish modal instead of leaving the user waiting.
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        artifact = Artifact(
            id=artifact_id,
            title=final_title,
            description=description.strip(),
            type=artifact_type,
            tags=tags,
            category=truncate_text(category.strip() or "general", 120),
            owner_name=truncate_text(owner_name.strip() or "You", 160),
            status="processing",
            object_key=object_key,
            original_filename=file.filename or object_key,
            content_type=file.content_type or "application/octet-stream",
            file_size=file_size,
            document_summary="Queued for background processing.",
            page_summaries=[],
        )
        db.add(artifact)
        db.flush()
        enqueue_artifact_processing(db, artifact.id)
        return artifact
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/metrics", response_model=MetricsOut)
def metrics(db: Session = Depends(get_db)):
    return MetricsOut(
        total_documents=db.scalar(select(func.count(Artifact.id))) or 0,
        total_comments=db.scalar(select(func.count(Comment.id))) or 0,
    )


@router.get("/artifacts", response_model=list[ArtifactOut])
def list_artifacts(
    q: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = "newest",
    db: Session = Depends(get_db),
):
    if sort not in ALLOWED_SORTS:
        raise HTTPException(status_code=400, detail=f"Invalid sort option. Use one of: {', '.join(sorted(ALLOWED_SORTS))}")

    comment_counts = (
        select(Comment.artifact_id, func.count(Comment.id).label("comment_count"))
        .group_by(Comment.artifact_id)
        .subquery()
    )

    statement = select(Artifact).outerjoin(comment_counts, Artifact.id == comment_counts.c.artifact_id)

    if type and type != "all":
        if type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="Invalid artifact type")
        statement = statement.where(Artifact.type == type)
    if status and status != "all":
        if status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid artifact status")
        statement = statement.where(Artifact.status == status)
    if q:
        pattern = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Artifact.title).like(pattern),
                func.lower(Artifact.description).like(pattern),
                func.lower(Artifact.category).like(pattern),
                func.lower(Artifact.type).like(pattern),
                func.lower(Artifact.status).like(pattern),
                func.lower(cast(Artifact.tags, String)).like(pattern),
                func.lower(Artifact.document_summary).like(pattern),
                func.lower(Artifact.feedback_summary).like(pattern),
            )
        )

    comment_count_expr = func.coalesce(comment_counts.c.comment_count, 0)
    if sort == "oldest":
        statement = statement.order_by(Artifact.created_at.asc())
    elif sort == "title_az":
        statement = statement.order_by(func.lower(Artifact.title).asc(), Artifact.created_at.desc())
    elif sort == "title_za":
        statement = statement.order_by(func.lower(Artifact.title).desc(), Artifact.created_at.desc())
    elif sort == "most_comments":
        statement = statement.order_by(comment_count_expr.desc(), Artifact.created_at.desc())
    elif sort == "least_comments":
        statement = statement.order_by(comment_count_expr.asc(), Artifact.created_at.desc())
    elif sort == "recently_updated":
        statement = statement.order_by(Artifact.updated_at.desc())
    elif sort == "recently_processed":
        statement = statement.order_by(Artifact.processed_at.desc().nulls_last(), Artifact.created_at.desc())
    elif sort == "status":
        statement = statement.order_by(Artifact.status.asc(), Artifact.created_at.desc())
    elif sort == "type":
        statement = statement.order_by(Artifact.type.asc(), Artifact.created_at.desc())
    else:
        statement = statement.order_by(Artifact.created_at.desc())

    artifacts = db.scalars(statement).all()
    return [artifact_to_out(db, artifact) for artifact in artifacts]


@router.post("/artifacts/bulk", response_model=list[ArtifactOut], status_code=status.HTTP_202_ACCEPTED)
async def create_artifacts_bulk(
    title: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    category: Annotated[str, Form()] = "general",
    owner_name: Annotated[str, Form()] = "You",
    tags: Annotated[str, Form()] = "[]",
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    parsed_tags = parse_tags(tags)
    artifacts = []
    try:
        for file in files:
            artifacts.append(
                await create_one_artifact(
                    db=db,
                    file=file,
                    title=title,
                    description=description,
                    category=category,
                    owner_name=owner_name,
                    tags=parsed_tags,
                    multiple=len(files) > 1,
                )
            )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Could not save artifact metadata. The uploaded file title or metadata was too long or invalid: {type(exc.orig).__name__ if getattr(exc, 'orig', None) else type(exc).__name__}",
        ) from exc

    for artifact in artifacts:
        db.refresh(artifact)
    return [artifact_to_out(db, artifact) for artifact in artifacts]


@router.post("/artifacts", response_model=ArtifactOut, status_code=status.HTTP_202_ACCEPTED)
async def create_artifact_legacy(
    title: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    category: Annotated[str, Form()] = "general",
    owner_name: Annotated[str, Form()] = "You",
    tags: Annotated[str, Form()] = "[]",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        artifact = await create_one_artifact(
            db=db,
            file=file,
            title=title,
            description=description,
            category=category,
            owner_name=owner_name,
            tags=parse_tags(tags),
            multiple=False,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Could not save artifact metadata. The uploaded file title or metadata was too long or invalid: {type(exc.orig).__name__ if getattr(exc, 'orig', None) else type(exc).__name__}",
        ) from exc
    db.refresh(artifact)
    return artifact_to_out(db, artifact)


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
def get_artifact(artifact_id: str, db: Session = Depends(get_db)):
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact_to_out(db, artifact)


@router.get("/files/{artifact_id}")
def get_file(artifact_id: str, request: Request, db: Session = Depends(get_db)):
    """Stream an artifact through the API so private blob storage can still preview in the browser.

    PDF viewers often request byte ranges. Supporting Range here makes embedded
    PDF previews much more reliable, and streaming avoids reading large files
    fully into backend memory.
    """
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    range_header = request.headers.get("range")
    try:
        obj = get_object_response(artifact.object_key, range_header)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    headers = {
        # Keep this header ASCII-only. Starlette encodes response headers as latin-1,
        # while uploaded filenames may contain Unicode characters such as U+202F.
        "Content-Disposition": content_disposition_inline(artifact.original_filename),
        "Cache-Control": "private, max-age=60",
        "Accept-Ranges": "bytes",
        "X-Content-Type-Options": "nosniff",
    }

    if obj.get("ContentLength") is not None:
        headers["Content-Length"] = str(obj["ContentLength"])
    if obj.get("ContentRange"):
        headers["Content-Range"] = obj["ContentRange"]

    status_code = 206 if range_header else 200
    return StreamingResponse(
        iter_streaming_body(obj["Body"]),
        status_code=status_code,
        media_type=artifact.content_type or "application/octet-stream",
        headers=latin1_headers(headers),
    )


@router.get("/artifacts/{artifact_id}/comments", response_model=list[CommentOut])
def list_comments(artifact_id: str, db: Session = Depends(get_db)):
    if not db.get(Artifact, artifact_id):
        raise HTTPException(status_code=404, detail="Artifact not found")
    return db.scalars(select(Comment).where(Comment.artifact_id == artifact_id).order_by(Comment.created_at.asc())).all()


@router.post("/artifacts/{artifact_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(artifact_id: str, payload: CommentCreate, db: Session = Depends(get_db)):
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Comment body is required")
    comment = Comment(artifact_id=artifact_id, author_name="You", body=body, kind=payload.kind)
    db.add(comment)
    db.flush()
    comments = db.scalars(select(Comment).where(Comment.artifact_id == artifact_id).order_by(Comment.created_at.asc())).all()
    artifact.feedback_summary = generate_feedback_summary(artifact, list(comments))
    artifact.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)
    return comment


@router.post("/artifacts/{artifact_id}/feedback-summary", response_model=FeedbackSummaryOut)
def refresh_feedback_summary(artifact_id: str, db: Session = Depends(get_db)):
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    comments = db.scalars(select(Comment).where(Comment.artifact_id == artifact_id).order_by(Comment.created_at.asc())).all()
    artifact.feedback_summary = generate_feedback_summary(artifact, list(comments))
    artifact.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(artifact)
    return FeedbackSummaryOut(feedback_summary=artifact.feedback_summary)


@router.post("/artifacts/{artifact_id}/summaries", response_model=DocumentSummaryOut, status_code=status.HTTP_202_ACCEPTED)
def refresh_document_summary(artifact_id: str, db: Session = Depends(get_db)):
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact.status = "processing"
    artifact.processing_error = None
    enqueue_artifact_processing(db, artifact.id)
    db.commit()
    db.refresh(artifact)
    return DocumentSummaryOut(document_summary=artifact.document_summary or "Queued for background processing.", page_summaries=artifact.page_summaries or [])


@router.get("/jobs", response_model=list[ProcessingJobOut])
def list_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(100)).all()


@router.post("/jobs/recover")
def recover_jobs(db: Session = Depends(get_db)):
    recovered = recover_stale_jobs(db)
    return {"recovered": recovered}


@router.post("/artifacts/{artifact_id}/share-links", response_model=ShareLinkOut, status_code=status.HTTP_201_CREATED)
def create_share_link(artifact_id: str, payload: ShareLinkCreate, db: Session = Depends(get_db)):
    if not db.get(Artifact, artifact_id):
        raise HTTPException(status_code=404, detail="Artifact not found")
    if payload.expires_in_hours not in {24, 36, 72}:
        raise HTTPException(status_code=400, detail="Share links can expire after 24, 36, or 72 hours")
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
    link = ShareLink(artifact_id=artifact_id, token=token, access=payload.access, expires_at=expires_at)
    db.add(link)
    db.commit()
    db.refresh(link)
    return ShareLinkOut(url=f"{settings.frontend_base_url.rstrip('/')}/share/{artifact_id}?token={token}", expires_at=link.expires_at, expires_in_hours=payload.expires_in_hours)


@router.get("/share/{artifact_id}", response_model=ArtifactOut)
def get_shared_artifact(artifact_id: str, token: str, db: Session = Depends(get_db)):
    link = db.scalar(select(ShareLink).where(ShareLink.artifact_id == artifact_id, ShareLink.token == token))
    if not link:
        raise HTTPException(status_code=404, detail="Shared link not found")
    expires_at = link.expires_at if link.expires_at.tzinfo else link.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Shared link expired")
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact_to_out(db, artifact)
