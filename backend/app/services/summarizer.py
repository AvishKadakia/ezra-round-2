from __future__ import annotations

import base64
import gc
import io
from dataclasses import dataclass
from pathlib import Path

import fitz
from openai import OpenAI
from PIL import Image

from app.core.config import get_settings

settings = get_settings()


@dataclass
class SummaryResult:
    document_summary: str
    page_summaries: list[dict]


def _vision_unavailable_summary(page_number: int, reason: str | None = None) -> str:
    """Fallback copy that does not talk about text extraction.

    The product behavior is image-first: PDF pages are rendered as images and then
    summarized by a vision-capable LLM. If the LLM is not configured or fails, the
    UI should say that visual summarization is unavailable instead of saying that
    text could not be extracted.
    """

    base = f"Page {page_number} visual summary is pending."
    if reason:
        return f"{base} {reason}"
    return f"{base} Configure OPENAI_API_KEY to generate page-level visual summaries."


def _fallback_document_summary(title: str, artifact_type: str, page_summaries: list[dict]) -> str:
    if page_summaries:
        usable = [p["summary"] for p in page_summaries if "pending" not in p["summary"].lower()]
        if usable:
            return (
                f"{title} is a {artifact_type.upper()} document with {len(page_summaries)} summarized page(s). "
                f"Main visual takeaway: {usable[0][:220]}"
            )
        return (
            f"{title} is a {artifact_type.upper()} document with {len(page_summaries)} page(s). "
            "Visual summarization is pending because the LLM vision service is not configured or failed."
        )
    return f"{title} is a {artifact_type.upper()} artifact uploaded for review."


def _summarize_image_with_llm(title: str, page_number: int, png_bytes: bytes) -> str:
    """Summarize a rendered page/image using vision only.

    No PDF text extraction is used here. For PDFs, the worker renders each page to
    a bounded-size PNG and asks the model to summarize what is visually present.
    """

    if not settings.openai_api_key:
        return _vision_unavailable_summary(page_number)

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"You are looking at page {page_number} of a document titled '{title}'. "
                                "Summarize only what is visible in this rendered page image. "
                                "Do not mention OCR, text extraction, or whether text was extractable. "
                                "Return 2 concise sentences focused on the page's main purpose, visible structure, "
                                "important labels, numbers, UI elements, or review-relevant details."
                            ),
                        },
                        {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"},
                    ],
                }
            ],
            temperature=0.2,
        )
        return response.output_text.strip() or _vision_unavailable_summary(page_number, "The model returned an empty summary.")
    except Exception as exc:
        # Keep the error actionable but safe for the UI.
        return _vision_unavailable_summary(
            page_number,
            f"Vision summarization failed: {type(exc).__name__}. Check OPENAI_API_KEY and OPENAI_MODEL.",
        )


def _aggregate_with_llm(title: str, artifact_type: str, page_summaries: list[dict]) -> str:
    fallback = _fallback_document_summary(title, artifact_type, page_summaries)
    if not settings.openai_api_key:
        return fallback
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        joined = "\n".join(f"Page {p['page_number']}: {p['summary']}" for p in page_summaries)
        response = client.responses.create(
            model=settings.openai_model,
            input=(
                "Create an overall document summary from these visual page summaries. "
                "Do not mention OCR or text extraction. Use 4 concise sentences maximum. "
                f"Title: {title}\n\n{joined}"
            ),
            temperature=0.2,
        )
        return response.output_text.strip() or fallback
    except Exception:
        return fallback


def _image_file_to_png_bytes(path: Path) -> bytes:
    with Image.open(path) as image:
        image.thumbnail((1400, 1400))
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        out = io.BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()


def _summarize_image_file(title: str, path: Path) -> SummaryResult:
    png_bytes = _image_file_to_png_bytes(path)
    summary = _summarize_image_with_llm(title, 1, png_bytes)
    pages = [{"page_number": 1, "summary": summary, "image_url": None}]
    return SummaryResult(document_summary=_aggregate_with_llm(title, "image", pages), page_summaries=pages)


def _page_to_png_bytes(page: fitz.Page) -> bytes:
    # Low DPI is deliberate: each page is treated as an image, but rendering is bounded
    # to reduce memory pressure for large multi-page PDFs.
    pix = page.get_pixmap(matrix=fitz.Matrix(1.15, 1.15), alpha=False)
    try:
        return pix.tobytes("png")
    finally:
        pix = None  # help release C memory before the next page
        gc.collect()


def _summarize_pdf_file(title: str, path: Path) -> SummaryResult:
    page_summaries: list[dict] = []
    try:
        with fitz.open(path) as doc:
            page_count = min(doc.page_count, settings.max_pdf_pages_to_summarize)
            for index in range(page_count):
                page_number = index + 1
                page = doc.load_page(index)
                try:
                    png_bytes = _page_to_png_bytes(page)
                    summary = _summarize_image_with_llm(title, page_number, png_bytes)
                    page_summaries.append({"page_number": page_number, "summary": summary, "image_url": None})
                except MemoryError:
                    page_summaries.append(
                        {
                            "page_number": page_number,
                            "summary": "This page was skipped because it exceeded available memory during visual rendering.",
                            "image_url": None,
                        }
                    )
                    gc.collect()
                finally:
                    page = None
                    gc.collect()
    except Exception as exc:
        page_summaries = [
            {
                "page_number": 1,
                "summary": f"PDF was uploaded, but visual page rendering failed during summary generation: {type(exc).__name__}.",
                "image_url": None,
            }
        ]
    return SummaryResult(document_summary=_aggregate_with_llm(title, "pdf", page_summaries), page_summaries=page_summaries)


def summarize_artifact_file(title: str, artifact_type: str, path: Path) -> SummaryResult:
    if artifact_type == "image":
        return _summarize_image_file(title, path)
    if artifact_type == "pdf":
        return _summarize_pdf_file(title, path)
    return SummaryResult(document_summary=_fallback_document_summary(title, artifact_type, []), page_summaries=[])
