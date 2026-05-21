from __future__ import annotations

import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Artifact, ProcessingJob
from app.services.storage import download_to_path
from app.services.summarizer import summarize_artifact_file

settings = get_settings()
ACTIVE_JOB_STATUSES = ("queued", "running")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_artifact_processing(db: Session, artifact_id: str) -> ProcessingJob:
    """Queue one processing job unless an active one already exists for the artifact."""

    active_count = db.scalar(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.artifact_id == artifact_id,
            ProcessingJob.status.in_(ACTIVE_JOB_STATUSES),
        )
    ) or 0
    if active_count:
        return db.scalars(
            select(ProcessingJob)
            .where(ProcessingJob.artifact_id == artifact_id, ProcessingJob.status.in_(ACTIVE_JOB_STATUSES))
            .order_by(ProcessingJob.created_at.desc())
            .limit(1)
        ).first()  # type: ignore[return-value]

    job = ProcessingJob(artifact_id=artifact_id, job_type="summarize_artifact", status="queued")
    db.add(job)
    return job


def claim_next_job(db: Session) -> ProcessingJob | None:
    """Atomically claim the next queued job.

    On PostgreSQL, FOR UPDATE SKIP LOCKED lets multiple workers run without
    claiming the same row. SQLite ignores this style of locking in local tests.
    """

    statement = (
        select(ProcessingJob)
        .where(ProcessingJob.status == "queued")
        .order_by(ProcessingJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.scalars(statement).first()
    if not job:
        return None

    job.status = "running"
    job.attempts += 1
    job.started_at = now_utc()
    job.updated_at = now_utc()
    db.commit()
    db.refresh(job)
    return job


def recover_stale_jobs(db: Session) -> int:
    """Recover jobs/artifacts that would otherwise stay Processing forever.

    This handles worker crashes, laptop sleep, OOM exits, and old artifacts left
    in processing state with no queued/running job.
    """

    recovered = 0
    current_time = now_utc()
    cutoff = current_time - timedelta(seconds=settings.worker_stale_job_seconds)

    stale_jobs = db.scalars(
        select(ProcessingJob).where(
            ProcessingJob.status == "running",
            ProcessingJob.updated_at < cutoff,
        )
    ).all()

    for job in stale_jobs:
        artifact = db.get(Artifact, job.artifact_id)
        if job.attempts < job.max_attempts:
            job.status = "queued"
            job.error = "Recovered stale running job after worker heartbeat timeout."
            job.updated_at = current_time
            if artifact and artifact.status != "ready":
                artifact.status = "processing"
                artifact.processing_error = None
        else:
            job.status = "failed"
            job.error = "Processing timed out too many times."
            job.finished_at = current_time
            job.updated_at = current_time
            if artifact and artifact.status != "ready":
                artifact.status = "failed"
                artifact.processing_error = job.error
        recovered += 1

    processing_artifacts = db.scalars(select(Artifact).where(Artifact.status == "processing")).all()
    for artifact in processing_artifacts:
        active_count = db.scalar(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.artifact_id == artifact.id,
                ProcessingJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        ) or 0
        if active_count == 0:
            enqueue_artifact_processing(db, artifact.id)
            artifact.processing_error = None
            recovered += 1

    if recovered:
        db.commit()
    else:
        db.rollback()
    return recovered


def requeue_failed_storage_download_jobs(db: Session) -> int:
    """Requeue artifacts that failed because the old worker download path was incompatible.

    The preview endpoint may still work for these artifacts because it streams via
    get_object(). After switching the worker to the same streaming path, this
    helper lets `make repair-processing` retry those previously failed records.
    """

    failed_artifacts = db.scalars(
        select(Artifact).where(
            Artifact.status == "failed",
            Artifact.processing_error.ilike("%Blob storage download failed: 403%"),
        )
    ).all()

    requeued = 0
    for artifact in failed_artifacts:
        active_count = db.scalar(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.artifact_id == artifact.id,
                ProcessingJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        ) or 0
        if active_count:
            continue

        artifact.status = "processing"
        artifact.processing_error = None
        enqueue_artifact_processing(db, artifact.id)
        requeued += 1

    if requeued:
        db.commit()
    else:
        db.rollback()
    return requeued


def heartbeat_job(db: Session, job: ProcessingJob) -> None:
    job.updated_at = now_utc()
    db.commit()


def process_job(db: Session, job: ProcessingJob) -> None:
    artifact = db.get(Artifact, job.artifact_id)
    if not artifact:
        job.status = "failed"
        job.error = "Artifact no longer exists"
        job.finished_at = now_utc()
        job.updated_at = now_utc()
        db.commit()
        return

    heartbeat_job(db, job)
    with tempfile.TemporaryDirectory(prefix="artifact-worker-") as tmp_dir:
        suffix = Path(artifact.original_filename).suffix or (".pdf" if artifact.type == "pdf" else ".bin")
        local_path = Path(tmp_dir) / f"{artifact.id}{suffix}"
        download_to_path(artifact.object_key, local_path)
        heartbeat_job(db, job)
        summary = summarize_artifact_file(artifact.title, artifact.type, local_path)

    artifact.document_summary = summary.document_summary
    artifact.page_summaries = summary.page_summaries
    artifact.status = "ready"
    artifact.processing_error = None
    artifact.processed_at = now_utc()
    artifact.updated_at = now_utc()

    job.status = "succeeded"
    job.error = None
    job.finished_at = now_utc()
    job.updated_at = now_utc()
    db.commit()


def fail_job(db: Session, job: ProcessingJob, error: BaseException) -> None:
    artifact = db.get(Artifact, job.artifact_id)
    message = f"{type(error).__name__}: {str(error)[:700]}"
    if job.attempts < job.max_attempts:
        job.status = "queued"
        if artifact and artifact.status != "ready":
            artifact.status = "processing"
            artifact.processing_error = message
    else:
        job.status = "failed"
        job.finished_at = now_utc()
        if artifact and artifact.status != "ready":
            artifact.status = "failed"
            artifact.processing_error = message
    job.error = message
    job.updated_at = now_utc()
    db.commit()


def run_recovery_once() -> int:
    db = SessionLocal()
    try:
        return recover_stale_jobs(db)
    finally:
        db.close()


def run_failed_storage_repair_once() -> int:
    db = SessionLocal()
    try:
        return requeue_failed_storage_download_jobs(db)
    finally:
        db.close()


def run_worker_forever() -> None:
    print("Artifact Hub worker started. Waiting for queued jobs...")
    last_recovery_at = 0.0
    while True:
        db = SessionLocal()
        try:
            current = time.monotonic()
            if current - last_recovery_at >= settings.worker_recovery_seconds:
                recovered = recover_stale_jobs(db)
                if recovered:
                    print(f"Recovered {recovered} stale processing job/artifact record(s).")
                last_recovery_at = current

            job = claim_next_job(db)
            if not job:
                time.sleep(settings.worker_poll_seconds)
                continue
            try:
                print(f"Processing job={job.id} artifact={job.artifact_id} attempt={job.attempts}")
                process_job(db, job)
                print(f"Finished job={job.id}")
            except BaseException as exc:  # includes MemoryError; do not let the worker die silently
                print(f"Job failed job={job.id}: {exc}")
                fail_job(db, job, exc)
        finally:
            db.close()
