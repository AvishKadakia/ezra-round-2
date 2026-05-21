from __future__ import annotations

from collections import Counter

from openai import OpenAI

from app.core.config import get_settings
from app.models import Artifact, Comment

settings = get_settings()


def _fallback_feedback_summary(artifact: Artifact, comments: list[Comment]) -> str | None:
    if not comments:
        return None

    kinds = Counter((comment.kind or "general") for comment in comments)
    latest = comments[-1].body.strip().replace("\n", " ")[:220]
    blockers = [comment.body.strip().replace("\n", " ") for comment in comments if comment.kind == "blocker"]
    questions = [comment.body.strip().replace("\n", " ") for comment in comments if comment.kind == "question"]

    signals: list[str] = []
    if blockers:
        signals.append(f"main blocker: {blockers[-1][:180]}")
    if questions:
        signals.append(f"open question: {questions[-1][:180]}")
    if not signals:
        signals.append(f"latest feedback: {latest}")

    kind_text = ", ".join(f"{label}: {count}" for label, count in sorted(kinds.items()))
    return f"{len(comments)} feedback item(s) recorded ({kind_text}). " + " ".join(signals)


def generate_feedback_summary(artifact: Artifact, comments: list[Comment]) -> str | None:
    """Summarize reviewer feedback for an artifact.

    This is intentionally separate from document_summary. document_summary describes
    the uploaded file; feedback_summary describes the review conversation and is
    regenerated whenever comments are added or by agent tools.
    """

    if not comments:
        return None

    fallback = _fallback_feedback_summary(artifact, comments)
    if not settings.openai_api_key:
        return fallback

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        comments_text = "\n".join(
            f"- {comment.author_name} [{comment.kind or 'general'}]: {comment.body}" for comment in comments[-30:]
        )
        response = client.responses.create(
            model=settings.openai_model,
            input=(
                "You are summarizing an artifact review conversation for an AI-agent workflow. "
                "Return 3 concise sentences maximum. Cover consensus, blockers, and next best action. "
                "Do not repeat every comment. Be specific and operational.\n\n"
                f"Artifact: {artifact.title}\n"
                f"Type: {artifact.type}\n"
                f"Status: {artifact.status}\n"
                f"Document summary: {artifact.document_summary or 'not available'}\n\n"
                f"Feedback comments:\n{comments_text}"
            ),
            temperature=0.2,
        )
        return response.output_text.strip() or fallback
    except Exception:
        return fallback
