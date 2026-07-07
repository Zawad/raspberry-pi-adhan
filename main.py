"""adhand — LAN adhan daemon + web app.

Run with: uvicorn main:app --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import db, scheduler
from routes import router
from config import WEB_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="adhand", lifespan=lifespan)
app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
