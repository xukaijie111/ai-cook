import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, ensure_database_exists, engine
from app.routers import dishes, prompts

logging.basicConfig(level=logging.INFO)

ensure_database_exists()
Base.metadata.create_all(bind=engine)


def _migrate_schema() -> None:
    inspector = inspect(engine)
    if "videos" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("videos")}
        if "oss_key" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE videos ADD COLUMN oss_key VARCHAR(255) NULL")
                )


_migrate_schema()

app = FastAPI(title="Cooking Agent API", version="1.0.0")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dishes.router)
app.include_router(prompts.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
