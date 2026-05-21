# Artifact Hub

## Phase 5 additions

- Added a remote FastMCP server at `GET/POST /mcp` using Streamable HTTP.
- Added MCP configuration endpoint at `/mcp-config` so users can paste a remote MCP URL into clients that support remote MCP servers, without a local bridge.
- Added agentic MCP tools for review triage, artifact briefs, feedback summarization, processing recovery, and safe share-link creation.
- Added automatic feedback summaries for artifacts with comments.
- Added gallery sorting: newest, oldest, title A-Z/Z-A, most/least comments, recently updated, recently processed, status, and type.

### MCP local test

Run the app, then open:

```txt
http://localhost:8000/mcp-config
```

The remote MCP endpoint is:

```txt
http://localhost:8000/mcp
```

For Railway, set:

```env
PUBLIC_API_BASE_URL=https://your-backend.up.railway.app
MCP_PUBLIC_URL=https://your-backend.up.railway.app/mcp
FRONTEND_BASE_URL=https://your-frontend.netlify.app
```


Full-stack Round 2 Artifact Hub implementation.

## Structure

```txt
/frontend  React + TypeScript + Vite + Netlify config
/backend   FastAPI + PostgreSQL + S3-compatible storage + Railway config
```

## What changed in this version

- Multi-file publish is asynchronous: HTTP requests upload raw files to blob storage, create artifacts, enqueue processing jobs, and return immediately.
- A separate background worker processes queued summaries so browser disconnects do not kill long PDF processing.
- PDF summarization is page-by-page to reduce memory pressure; each page is rendered independently and summarized before aggregation.
- File restrictions are strict: images and PDFs only, 10 MB maximum per file, validated on both frontend and backend.
- Publish modal file list is scrollable, while action buttons remain pinned to the bottom of the modal.
- Long text is protected with truncation/line-clamping across cards, nav-adjacent text, comments, and metadata.
- Upload timestamp is shown inline next to the document type on the artifact page.
- Root `Makefile` adds `make install`, `make dev`, and `make build`.

## Local development

Fast path:

```bash
make install
make dev
```

This starts the frontend, backend, and background worker together.

Manual backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Manual worker:

```bash
cd backend
source .venv/bin/activate
python -m app.worker
```

Manual frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Key flows

- Bulk publish multiple PDFs/images at once.
- Browse gallery with metrics cards and animated search.
- Click entire card to inspect artifact.
- PDF preview on gallery card and inspection page.
- Inspection page shows inline type/upload time, plus document summary.
- Toggle between overall summary and page-level summaries.
- Generate share links for 24h, 36h, or 72h.
- MCP config modal gives placeholder bot configuration.

## Deployment

Frontend: deploy `/frontend` to Netlify. `frontend/netlify.toml` sets the build command, publish directory, and SPA redirects.

Backend API: deploy `/backend` to Railway using `backend/railway.toml`.

Backend worker: create a second Railway service from `/backend` using `backend/railway.worker.toml` or set its start command to:

```bash
python -m app.worker
```

Both Railway services need the same database, bucket, and OpenAI environment variables.

## Security note

The provided database and storage values are treated as challenge placeholders in `backend/.env.example`. Rotate them before pushing to a public repository if they are active credentials.

## v4 visual-summary patch

PDF summaries are now image-first only. The worker renders each PDF page to a PNG and sends the rendered page image to the configured vision-capable LLM. It no longer calls `page.get_text()` and it no longer displays the misleading "no extractable text" message. If `OPENAI_API_KEY` is missing or the vision request fails, the UI shows a clear "visual summary pending" message instead.

After applying this patch to an existing artifact, click **Refresh** in the Document summary panel, or re-upload the file, so the worker regenerates the saved page summaries.
## Railway bucket SSL note

If uploads fail locally with `SSL validation failed ... [Errno 2] No such file or directory`, boto3 is usually trying to use a missing CA certificate bundle from your local Python/AWS environment. This version passes `certifi.where()` directly to boto3 by default. Run `make install` again so `certifi` is installed, keep `S3_CA_BUNDLE` blank unless it points to a real `.pem` file, then restart `make dev`.



## Processing recovery

If cards stay in **Processing** after a worker crash, laptop sleep, OOM, or failed previous run, use:

```bash
make repair-processing
```

The worker also runs automatic recovery every few seconds. It requeues stale `running` jobs and creates a missing job for any artifact still marked `processing` without an active queued/running job.

Generated artifact IDs are now capped to fit the existing PostgreSQL `VARCHAR(80)` primary key, while user-facing titles are separately truncated to a safe display/storage length.