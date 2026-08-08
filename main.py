import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import users_collection
from observability import configure_logging, instrument
from routes import auth

# Before anything else in this module can log, so no line escapes as plain
# text during import.
configure_logging()

logger = logging.getLogger("auth-service")

app = FastAPI(title="Sports Store — Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# AFTER add_middleware, deliberately. Starlette builds its middleware stack so
# that the last one added is the outermost, so registering here means the
# metrics middleware wraps CORS rather than sitting inside it — and the
# latency histogram measures the whole request as a client experiences it.
instrument(app)

app.include_router(auth.router, prefix="/api")


@app.on_event("startup")
async def create_indexes():
    try:
        await users_collection.create_index("email", unique=True)
    except Exception as exc:  # Mongo may be unavailable (e.g. unit tests)
        logger.warning("Index creation skipped: %s", exc)


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth-service"}
