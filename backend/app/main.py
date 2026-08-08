import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, chat, files, projects, prompts

settings = get_settings()
logger = logging.getLogger(__name__)


def _init_db(max_retries: int = 30, delay: float = 2.0) -> None:
    """Wait for database, create tables, and ensure schema migrations."""
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            with engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE conversations ADD COLUMN is_starred BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                except Exception:
                    pass
            logger.info("Database ready")
            return
        except OperationalError as exc:
            if attempt == max_retries:
                raise
            logger.warning("Database not ready (attempt %s/%s): %s", attempt, max_retries, exc)
            time.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    description="Minimal Chatbot Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(files.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": settings.app_name}
