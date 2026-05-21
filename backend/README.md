# Artifact Hub FastAPI Backend

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

In a second terminal, run the worker:

```bash
source .venv/bin/activate
python -m app.worker
```

Open:

```txt
http://localhost:8000/docs
```

## Async processing model

The upload endpoints do only the fast work:

1. Validate type and 10 MB size limit.
2. Stream raw file bytes to S3-compatible storage.
3. Create an artifact row with `status=processing`.
4. Create a `processing_jobs` row.
5. Return `202 Accepted` immediately.

The worker polls `processing_jobs`, downloads one artifact at a time, renders PDF pages one by one, and writes page + document summaries back to the artifact record.

## Important routes

```txt
GET  /artifacts
POST /artifacts
POST /artifacts/bulk
GET  /jobs
POST /artifacts/{artifact_id}/comments
POST /artifacts/{artifact_id}/summaries
POST /artifacts/{artifact_id}/share-links
GET  /share/{artifact_id}?token={token}
```

## File policy

Allowed:

```txt
PDF, PNG, JPG/JPEG, WEBP, GIF
```

Rejected:

```txt
HTML, Markdown, TXT, DOC, DOCX, ZIP, unknown MIME/extensions, files larger than 10 MB
```
## Railway bucket SSL note

If uploads fail locally with `SSL validation failed ... [Errno 2] No such file or directory`, boto3 is usually trying to use a missing CA certificate bundle from your local Python/AWS environment. This version passes `certifi.where()` directly to boto3 by default. Run `make install` again so `certifi` is installed, keep `S3_CA_BUNDLE` blank unless it points to a real `.pem` file, then restart `make dev`.



## MCP server

The backend exposes a remote FastMCP server at `/mcp`. It is designed for AI agents, not just CRUD:

- `search_artifacts_for_review`
- `get_artifact_review_brief`
- `triage_review_queue`
- `add_structured_feedback`
- `refresh_feedback_summary`
- `queue_document_processing`
- `create_review_share_link`
- `plan_artifact_review_work`

Config snippets are available at `/mcp-config`.
