# backend/app/main.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.db.session import DatabaseManager
from backend.app.routers.auth import router as auth_router
from backend.app.routers.districts import router as districts_router
from backend.app.routers.dispatcher import router as dispatcher_router
from backend.app.routers.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = DatabaseManager(
        settings.DATABASE_URL,
        create_schema=settings.ENV == "dev",
    )
    async with db:
        app.state.db_manager = db
        yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- отдача сгенерированных HTML-карт ---
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth_router)
app.include_router(districts_router)
app.include_router(dispatcher_router)
app.include_router(users_router)