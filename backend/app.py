"""Main FastAPI application entrypoint."""

import sys
from pathlib import Path

# Ensure root directory is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routes.auth import router as auth_router
from backend.routes.config import router as config_router
from backend.routes.trading import router as trading_router
from backend.routes.backtest import router as backtest_router
from backend.routes.agent import router as agent_router

app = FastAPI(
    title="Stock Trading Agent Dashboard API",
    version="1.0.0",
    docs_url="/docs",
)

# CORS setup for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(trading_router)
app.include_router(backtest_router)
app.include_router(agent_router)

# Mount frontend production build if present
frontend_dist = ROOT_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {
            "message": "Stock Trading Agent Backend API Running",
            "docs": "/docs",
            "frontend_status": "Vite React dev server running on http://localhost:5173",
        }
