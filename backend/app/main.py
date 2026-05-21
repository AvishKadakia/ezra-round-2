from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.artifacts import router as artifact_router
from app.core.config import get_settings
from app.db.init_db import init_db
from app.mcp_server import mcp
from app.schemas import HealthOut

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Compact challenge-friendly setup. Swap for Alembic before serious production use.
    init_db()
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Artifact Hub API", version="0.5.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(artifact_router)


@app.get("/health", response_model=HealthOut)
def health():
    return HealthOut(ok=True, service="artifact-hub-api")


@app.get("/mcp-config")
def mcp_config():
    """Remote MCP configuration snippets for external AI agents.

    The important UX change is that users only need the deployed MCP URL. There
    is no local npx bridge or project-specific CLI setup.
    """

    url = settings.resolved_mcp_url
    return {
        "serverName": "artifact-hub",
        "remoteMcpUrl": url,
        "capabilities": [
            "search_artifacts_for_review",
            "get_artifact_review_brief",
            "triage_review_queue",
            "add_structured_feedback",
            "refresh_feedback_summary",
            "queue_document_processing",
            "create_review_share_link",
            "plan_artifact_review_work",
            "publish_artifact_from_base64",
        ],
        "claude": {
            "directUrl": url,
            "messagesApiExample": {
                "mcp_servers": [
                    {
                        "type": "url",
                        "name": "artifact-hub",
                        "url": url,
                    }
                ]
            },
        },
        "codex": {
            "directUrl": url,
            "configTomlExample": f'[mcp_servers.artifact-hub]\nurl = "{url}"',
        },
        "note": "Use the remote URL directly in clients that support remote Streamable HTTP MCP. No local bridge is required for this server.",
    }


# Remote Streamable HTTP MCP server. Clients connect to /mcp.
app.mount("/mcp", mcp.streamable_http_app())
