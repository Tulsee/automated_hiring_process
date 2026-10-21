import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.logging_config import setup_logging
from app.core.tracing import setup_tracing
from app.db.mongodb import close_mongodb, connect_mongodb, ensure_indexes
from app.db.qdrant import close_qdrant, connect_qdrant
from app.routes.applications import router as applications_router
from app.routes.jobs import router as jobs_router
from app.routes.hiring import router as hiring_router
from app.routes.interviews import router as interviews_router
from app.routes.auth import router as auth_router
from app.routes.notifications import router as notifications_router
from app.services.bootstrap import bootstrap_auth

from app.services.qdrant_service import create_collection

setup_logging()
setup_tracing()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Hiring Agent...")

    mongo_ok = await connect_mongodb()
    qdrant_ok = await connect_qdrant()

    logger.info("Database connection status")
    logger.info("MongoDB : %s", "CONNECTED" if mongo_ok else "FAILED")
    logger.info("Qdrant  : %s", "CONNECTED" if qdrant_ok else "FAILED")

    if not (mongo_ok and qdrant_ok):
        logger.warning("Starting with one or more database connections unavailable")

    if mongo_ok:
        await ensure_indexes()
        # The superadmin and default roles must exist before anyone signs in.
        await bootstrap_auth()

    if qdrant_ok:
        await create_collection()
    else:
        logger.warning(
            "Skipping Qdrant collection setup; screening will fail until "
            "Qdrant is reachable"
        )

    yield

    logger.info("Shutting down...")

    await close_mongodb()
    await close_qdrant()


app = FastAPI(title="Automated Hiring Process", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(hiring_router)
app.include_router(interviews_router)
app.include_router(notifications_router)


# The recruiter dashboard is a built React app. Serving it from the API keeps
# everything same-origin, so no CORS config is needed.
DASHBOARD_DIR = Path("app/static/dashboard")


# The single-page app uses real URLs for its public entry points
# (/dashboard/admin, /dashboard/apply) so the two sign-ins are shareable and
# survive a reload. StaticFiles only serves files, so these sub-paths are
# mapped to index.html explicitly, *before* the mount, which otherwise 404s
# them. The SPA then reads the path and shows the right screen.
SPA_ENTRY_PATHS = ("/dashboard/admin", "/dashboard/apply")


async def _serve_dashboard_index():
    index = DASHBOARD_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Dashboard build not found")


for _spa_path in SPA_ENTRY_PATHS:
    app.add_api_route(_spa_path, _serve_dashboard_index, methods=["GET"])


if DASHBOARD_DIR.exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=DASHBOARD_DIR, html=True),
        name="dashboard",
    )
else:
    logger.info("Dashboard build not found; run `npm run build` in Frontend/")


@app.get("/interview")
async def interview_page():
    """The candidate's interview, reached from their invite link.

    Served by the React app, which reads the `?token=` query parameter. The
    URL is kept as `/interview` so invite links already in candidates' inboxes
    keep working, even though the app's assets live under `/dashboard/`.

    The original standalone recorder is still on disk and is used as a fallback
    when the frontend has not been built.
    """
    dashboard_index = DASHBOARD_DIR / "index.html"

    if dashboard_index.exists():
        return FileResponse(dashboard_index)

    logger.warning(
        "Dashboard build not found; serving the standalone recorder instead"
    )

    return FileResponse("app/static/interview.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
