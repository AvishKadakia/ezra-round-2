from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from urllib.parse import urlparse
import base64
import binascii
import tempfile
from pathlib import Path


from mcp.server.transport_security import TransportSecuritySettings
from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Artifact, Comment, ProcessingJob, ShareLink
from app.services.feedback import generate_feedback_summary
from app.services.queue import enqueue_artifact_processing, recover_stale_jobs
from app.services.storage import StorageError, upload_fileobj
from app.api.artifacts import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_PDF_EXTENSIONS,
    MAX_TITLE_PREFIX_CHARS,
    build_artifact_id,
    build_artifact_title,
    detect_artifact_type,
    parse_tags,
    truncate_text,
)

settings = get_settings()

def _host_from_url(url: str) -> str | None:
    if not url:
        return None

    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    host = host.strip().strip("/")
    return host or None


def _allowed_hosts() -> list[str]:
    hosts = {
        "localhost:*",
        "127.0.0.1:*",
        "0.0.0.0:*",
    }

    for value in [
        settings.public_api_base_url,
        settings.mcp_public_url,
    ]:
        host = _host_from_url(value)
        if host:
            hosts.add(host)
            hosts.add(f"{host}:*")

    for host in settings.mcp_allowed_host_list:
        hosts.add(host)
        if ":" not in host:
            hosts.add(f"{host}:*")

    return sorted(hosts)


def _allowed_origins() -> list[str]:
    origins = {
        "http://localhost:6274",
        "http://127.0.0.1:6274",
        "http://localhost:*",
        "http://127.0.0.1:*",
    }

    for origin in settings.mcp_allowed_origin_list:
        origins.add(origin)

    return sorted(origins)


mcp = FastMCP(
    name="Artifact Hub Agent MCP",
    instructions=(
        "Artifact Hub exposes agentic review workflows for generated artifacts. "
        "Prefer tools that return review briefs, triage plans, feedback summaries, and safe next actions. "
        "Do not treat this as a raw CRUD API; use the context-rich tools to plan and execute artifact review work."
    ),
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=not settings.mcp_disable_dns_rebinding_protection,
        allowed_hosts=_allowed_hosts(),
        allowed_origins=_allowed_origins(),
    ),
)
# Mount this server at /mcp without requiring a nested /mcp path.
mcp.settings.streamable_http_path = "/"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _comment_count(db, artifact_id: str) -> int:
    return db.scalar(select(func.count(Comment.id)).where(Comment.artifact_id == artifact_id)) or 0


def _artifact_brief(db, artifact: Artifact, include_comments: bool = False) -> dict:
    comments = []
    if include_comments:
        comments = db.scalars(
            select(Comment).where(Comment.artifact_id == artifact.id).order_by(Comment.created_at.asc())
        ).all()
    count = len(comments) if include_comments else _comment_count(db, artifact.id)
    feedback_summary = artifact.feedback_summary
    if count and not feedback_summary:
        if not include_comments:
            comments = db.scalars(
                select(Comment).where(Comment.artifact_id == artifact.id).order_by(Comment.created_at.asc())
            ).all()
        feedback_summary = generate_feedback_summary(artifact, list(comments))

    payload = {
        "id": artifact.id,
        "title": artifact.title,
        "type": artifact.type,
        "status": artifact.status,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        "processed_at": artifact.processed_at.isoformat() if artifact.processed_at else None,
        "comment_count": count,
        "tags": artifact.tags or [],
        "category": artifact.category,
        "owner_name": artifact.owner_name,
        "document_summary": artifact.document_summary,
        "feedback_summary": feedback_summary,
        "processing_error": artifact.processing_error,
        "next_best_actions": _next_best_actions(artifact, count),
    }
    if include_comments:
        payload["comments"] = [
            {
                "id": comment.id,
                "author_name": comment.author_name,
                "kind": comment.kind,
                "body": comment.body,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
            }
            for comment in comments
        ]
    return payload


def _next_best_actions(artifact: Artifact, comment_count: int) -> list[str]:
    actions: list[str] = []
    if artifact.status == "processing":
        actions.append("Wait for the background worker, then refresh the artifact brief before making review decisions.")
    if artifact.status == "failed":
        actions.append("Queue document-summary processing again after checking the processing_error.")
    if artifact.status == "ready" and not artifact.document_summary:
        actions.append("Queue document-summary processing so reviewers have a document overview.")
    if comment_count and not artifact.feedback_summary:
        actions.append("Generate a feedback summary to compress the review conversation.")
    if not comment_count:
        actions.append("Ask reviewers for structured feedback or add an initial review comment.")
    actions.append("Create a short-lived share link only when the artifact is ready to send externally.")
    return actions


def _search_statement(query: str | None, status: str, artifact_type: str):
    statement = select(Artifact)
    if status != "all":
        statement = statement.where(Artifact.status == status)
    if artifact_type != "all":
        statement = statement.where(Artifact.type == artifact_type)
    if query:
        q = f"%{query.strip().lower()}%"
        statement = statement.where(
            func.lower(Artifact.title).like(q)
            | func.lower(Artifact.description).like(q)
            | func.lower(Artifact.category).like(q)
            | func.lower(Artifact.document_summary).like(q)
            | func.lower(Artifact.feedback_summary).like(q)
        )
    return statement.order_by(Artifact.updated_at.desc())


@mcp.tool(title="Search artifacts for review")
def search_artifacts_for_review(
    query: str = "",
    status: Literal["all", "processing", "ready", "failed", "archived"] = "all",
    artifact_type: Literal["all", "image", "pdf"] = "all",
    limit: int = 10,
) -> dict:
    """Find artifacts and return review-ready context, not just raw rows.

    Use this first when an agent needs to understand what exists, find items that
    need attention, or pick a candidate artifact for a follow-up action.
    """

    limit = max(1, min(limit, 25))
    db = SessionLocal()
    try:
        artifacts = db.scalars(_search_statement(query or None, status, artifact_type).limit(limit)).all()
        return {
            "count": len(artifacts),
            "artifacts": [_artifact_brief(db, artifact) for artifact in artifacts],
        }
    finally:
        db.close()


@mcp.tool(title="Get artifact review brief")
def get_artifact_review_brief(artifact_id: str) -> dict:
    """Return a complete agent brief for a single artifact.

    Includes document summary, feedback summary, comments, processing state,
    errors, and recommended next actions so agents can reason over the review.
    """

    db = SessionLocal()
    try:
        artifact = db.get(Artifact, artifact_id)
        if not artifact:
            return {"ok": False, "error": "Artifact not found", "artifact_id": artifact_id}
        return {"ok": True, "artifact": _artifact_brief(db, artifact, include_comments=True)}
    finally:
        db.close()


@mcp.tool(title="Triage review queue")
def triage_review_queue(limit: int = 12) -> dict:
    """Prioritize artifacts for an agent-driven review session.

    The result groups failed, processing, and ready-with-comments artifacts so an
    agent can decide whether to recover jobs, summarize feedback, or ask for review.
    """

    limit = max(1, min(limit, 30))
    db = SessionLocal()
    try:
        recover_stale_jobs(db)
        failed = db.scalars(select(Artifact).where(Artifact.status == "failed").order_by(Artifact.updated_at.desc()).limit(limit)).all()
        processing = db.scalars(select(Artifact).where(Artifact.status == "processing").order_by(Artifact.updated_at.desc()).limit(limit)).all()
        ready = db.scalars(select(Artifact).where(Artifact.status == "ready").order_by(Artifact.updated_at.desc()).limit(limit)).all()
        ready_with_comments = [artifact for artifact in ready if _comment_count(db, artifact.id) > 0][:limit]
        return {
            "failed": [_artifact_brief(db, artifact) for artifact in failed],
            "processing": [_artifact_brief(db, artifact) for artifact in processing],
            "ready_with_feedback": [_artifact_brief(db, artifact) for artifact in ready_with_comments],
            "guidance": [
                "Recover failed or stale jobs before requesting human review.",
                "For ready artifacts with comments, refresh feedback summaries before making decisions.",
                "Use create_review_share_link only after the artifact is ready and feedback blockers are understood.",
            ],
        }
    finally:
        db.close()


@mcp.tool(title="Add structured feedback")
def add_structured_feedback(
    artifact_id: str,
    body: str,
    kind: Literal["question", "decision", "blocker", "praise"] = "question",
) -> dict:
    """Add feedback and automatically regenerate the feedback summary.

    Use this when an agent is collecting reviewer decisions, blockers, or action
    items. It returns the updated review brief.
    """

    db = SessionLocal()
    try:
        artifact = db.get(Artifact, artifact_id)
        if not artifact:
            return {"ok": False, "error": "Artifact not found", "artifact_id": artifact_id}
        cleaned = body.strip()
        if not cleaned:
            return {"ok": False, "error": "Feedback body cannot be empty", "artifact_id": artifact_id}
        comment = Comment(artifact_id=artifact_id, author_name="MCP agent", body=cleaned, kind=kind)
        db.add(comment)
        db.flush()
        comments = db.scalars(select(Comment).where(Comment.artifact_id == artifact_id).order_by(Comment.created_at.asc())).all()
        artifact.feedback_summary = generate_feedback_summary(artifact, list(comments))
        artifact.updated_at = _now()
        db.commit()
        db.refresh(artifact)
        return {"ok": True, "artifact": _artifact_brief(db, artifact, include_comments=True)}
    finally:
        db.close()


@mcp.tool(title="Refresh feedback summary")
def refresh_feedback_summary(artifact_id: str) -> dict:
    """Regenerate the feedback summary for an artifact with comments."""

    db = SessionLocal()
    try:
        artifact = db.get(Artifact, artifact_id)
        if not artifact:
            return {"ok": False, "error": "Artifact not found", "artifact_id": artifact_id}
        comments = db.scalars(select(Comment).where(Comment.artifact_id == artifact_id).order_by(Comment.created_at.asc())).all()
        artifact.feedback_summary = generate_feedback_summary(artifact, list(comments))
        artifact.updated_at = _now()
        db.commit()
        db.refresh(artifact)
        return {"ok": True, "feedback_summary": artifact.feedback_summary, "artifact": _artifact_brief(db, artifact)}
    finally:
        db.close()


@mcp.tool(title="Queue document processing")
def queue_document_processing(artifact_id: str) -> dict:
    """Queue or requeue background processing for an artifact summary.

    Use this after a failed or stale processing state, or when the agent needs a
    fresh visual/document summary.
    """

    db = SessionLocal()
    try:
        artifact = db.get(Artifact, artifact_id)
        if not artifact:
            return {"ok": False, "error": "Artifact not found", "artifact_id": artifact_id}
        artifact.status = "processing"
        artifact.processing_error = None
        enqueue_artifact_processing(db, artifact.id)
        db.commit()
        return {"ok": True, "message": "Artifact processing queued", "artifact": _artifact_brief(db, artifact)}
    finally:
        db.close()


@mcp.tool(title="Create review share link")
def create_review_share_link(
    artifact_id: str,
    expires_in_hours: Literal[24, 36, 72] = 24,
) -> dict:
    """Create a short-lived link only after checking artifact readiness.

    The response includes warnings when the artifact is not ready or feedback has
    unresolved blockers so an agent can decide whether to proceed.
    """

    db = SessionLocal()
    try:
        artifact = db.get(Artifact, artifact_id)
        if not artifact:
            return {"ok": False, "error": "Artifact not found", "artifact_id": artifact_id}
        token = __import__("secrets").token_urlsafe(32)
        expires_at = _now() + timedelta(hours=expires_in_hours)
        link = ShareLink(artifact_id=artifact_id, token=token, access="anyone_with_link", expires_at=expires_at)
        db.add(link)
        db.commit()
        warnings = []
        if artifact.status != "ready":
            warnings.append(f"Artifact status is {artifact.status}; consider waiting until ready before sharing.")
        if artifact.feedback_summary and "blocker" in artifact.feedback_summary.lower():
            warnings.append("Feedback summary mentions a blocker; confirm before sharing externally.")
        return {
            "ok": True,
            "url": f"{settings.frontend_base_url.rstrip('/')}/share/{artifact_id}?token={token}",
            "expires_at": expires_at.isoformat(),
            "warnings": warnings,
        }
    finally:
        db.close()

def _safe_mcp_filename(filename: str) -> str:
    name = Path(filename or "mcp-artifact").name
    suffix = Path(name).suffix.lower()

    if suffix not in ALLOWED_IMAGE_EXTENSIONS and suffix not in ALLOWED_PDF_EXTENSIONS:
        raise ValueError("Only image files and PDFs are supported.")

    return name


def _content_type_from_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"

    return "application/octet-stream"


def _decode_base64_file(file_base64: str) -> bytes:
    cleaned = file_base64.strip()

    # Accept normal base64 and data URLs like:
    # data:application/pdf;base64,JVBERi0x...
    if "," in cleaned and cleaned.lower().startswith("data:"):
        cleaned = cleaned.split(",", 1)[1]

    try:
        return base64.b64decode(cleaned, validate=True)
    except binascii.Error as exc:
        raise ValueError("file_base64 is not valid base64.") from exc


@mcp.tool(title="Publish artifact from base64 file")
def publish_artifact_from_base64(
    filename: str,
    file_base64: str,
    title_prefix: str = "",
    description: str = "",
    category: str = "general",
    tags: list[str] | None = None,
    owner_name: str = "MCP agent",
) -> dict:
    """Upload a local file through remote MCP using base64 content.

    This is the no-local-setup upload path for chatbots. The user attaches a file
    to the chatbot; the agent passes the file name and base64 bytes to this tool.
    The backend validates the file, stores it in blob storage, creates the artifact,
    and queues background summarization.
    """

    temp_path: Path | None = None
    db = SessionLocal()

    try:
        filename = _safe_mcp_filename(filename)

        if len(title_prefix.strip()) > MAX_TITLE_PREFIX_CHARS:
            return {
                "ok": False,
                "error": f"title_prefix must be {MAX_TITLE_PREFIX_CHARS} characters or fewer",
            }

        file_bytes = _decode_base64_file(file_base64)

        if not file_bytes:
            return {"ok": False, "error": "Uploaded file is empty."}

        if len(file_bytes) > settings.max_upload_bytes:
            return {
                "ok": False,
                "error": f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB upload limit.",
            }

        suffix = Path(filename).suffix.lower()[:20]
        with tempfile.NamedTemporaryFile(prefix="mcp-upload-", suffix=suffix, delete=False) as temp:
            temp.write(file_bytes)
            temp.flush()
            temp_path = Path(temp.name)

        content_type = _content_type_from_filename(filename)
        artifact_type = detect_artifact_type(temp_path, filename, content_type)

        final_title = build_artifact_title(title_prefix.strip(), filename, multiple=False)
        artifact_id = build_artifact_id(final_title)
        object_key = f"artifacts/{artifact_id}{suffix}"

        try:
            with temp_path.open("rb") as buffer:
                upload_fileobj(object_key, buffer, content_type)
        except StorageError as exc:
            return {"ok": False, "error": str(exc)}

        parsed_tags = parse_tags(",".join(tags or []))

        artifact = Artifact(
            id=artifact_id,
            title=final_title,
            description=description.strip(),
            type=artifact_type,
            tags=parsed_tags,
            category=truncate_text(category.strip() or "general", 120),
            owner_name=truncate_text(owner_name.strip() or "MCP agent", 160),
            status="processing",
            object_key=object_key,
            original_filename=filename,
            content_type=content_type,
            file_size=len(file_bytes),
            document_summary="Queued for background processing.",
            page_summaries=[],
        )

        db.add(artifact)
        db.flush()
        enqueue_artifact_processing(db, artifact.id)
        db.commit()
        db.refresh(artifact)

        return {
            "ok": True,
            "message": "Artifact uploaded through MCP and queued for processing.",
            "artifact": _artifact_brief(db, artifact),
        }

    except ValueError as exc:
        db.rollback()
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        db.rollback()
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    finally:
        db.close()
        if temp_path:
            temp_path.unlink(missing_ok=True)

@mcp.tool(title="Plan artifact review work")
def plan_artifact_review_work(goal: str, query: str = "", limit: int = 8) -> dict:
    """Produce an agentic plan before mutating Artifact Hub state.

    Use this for ambiguous goals such as 'prepare assets for legal review' or
    'find artifacts that need follow-up'. It returns candidate artifacts and an
    ordered action plan grounded in current state.
    """

    db = SessionLocal()
    try:
        artifacts = db.scalars(_search_statement(query or None, "all", "all").limit(max(1, min(limit, 20)))).all()
        briefs = [_artifact_brief(db, artifact) for artifact in artifacts]
        plan = [
            "Inspect candidate artifacts with get_artifact_review_brief before changing state.",
            "Refresh document summaries for failed, stale, or unsummarized artifacts.",
            "Generate or refresh feedback summaries for artifacts with comments.",
            "Only create share links after blockers are understood and artifact status is ready.",
        ]
        return {"goal": goal, "candidate_count": len(briefs), "candidates": briefs, "recommended_plan": plan}
    finally:
        db.close()


@mcp.resource("artifact-hub://overview", mime_type="application/json")
def artifact_hub_overview() -> dict:
    """Current Artifact Hub status for agent grounding."""
    db = SessionLocal()
    try:
        return {
            "total_artifacts": db.scalar(select(func.count(Artifact.id))) or 0,
            "total_comments": db.scalar(select(func.count(Comment.id))) or 0,
            "processing": db.scalar(select(func.count(Artifact.id)).where(Artifact.status == "processing")) or 0,
            "failed": db.scalar(select(func.count(Artifact.id)).where(Artifact.status == "failed")) or 0,
            "ready": db.scalar(select(func.count(Artifact.id)).where(Artifact.status == "ready")) or 0,
        }
    finally:
        db.close()


@mcp.resource("artifact-hub://artifact/{artifact_id}", mime_type="application/json")
def artifact_resource(artifact_id: str) -> dict:
    """A complete artifact review resource addressable by artifact id."""
    return get_artifact_review_brief(artifact_id)


@mcp.prompt(title="Triage Artifact Hub review queue")
def triage_prompt() -> str:
    return (
        "Use Artifact Hub MCP tools to triage the current review queue. "
        "Start with triage_review_queue, inspect failed and ready-with-feedback artifacts, "
        "refresh summaries when needed, and return prioritized next actions with artifact IDs."
    )


@mcp.prompt(title="Prepare artifact for external sharing")
def prepare_for_sharing_prompt(artifact_id: str) -> str:
    return (
        f"Prepare artifact {artifact_id} for external sharing. First call get_artifact_review_brief. "
        "Check status, document summary, comments, feedback summary, and blockers. "
        "If safe, create a 24h review share link; otherwise explain the blockers and next actions."
    )
