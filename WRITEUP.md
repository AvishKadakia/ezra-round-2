# Artifact Hub Writeup

## What I built and why

Artifact Hub is a gallery-first review workspace for AI-generated files. It supports publishing images/PDFs, browsing, comments, share links, and document summaries.

## Architecture overview

The app is split into `/frontend` and `/backend`. The frontend is React/Vite and deploys to Netlify. The backend is FastAPI and deploys to Railway. A second Railway service runs the background worker.

Uploads are now asynchronous. The API streams raw files to blob storage and creates database jobs. The worker processes summaries out of band so large PDFs do not keep the browser request open.

## LLM usage

The worker treats PDFs as page images, summarizes each page, and aggregates page summaries into an overall document summary. Image uploads are summarized as single-page artifacts.

## MCP integration

The UI includes an MCP configuration modal with placeholder snippets for external bot integration. The backend exposes `/mcp/config` as the configuration source.

## What I chose not to build

I did not add full auth/RBAC or production-grade queue infrastructure. The current DB-backed queue is sufficient for the challenge and can be replaced with Redis/RQ, Celery, or a managed queue later.

## What I would do next

- Add signed direct-to-storage upload URLs.
- Add Redis/RQ or Celery for multi-worker concurrency.
- Add Alembic migrations.
- Add authentication and team permissions.
- Move secrets into Railway/Netlify environment variables only.
