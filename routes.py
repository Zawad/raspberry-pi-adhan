from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

import audio, db, hooks, scheduler
from config import CALC_METHODS, PRAYER_NAMES
from events import emit, ws_manager
from player import list_media, player

router = APIRouter()


# ---------- status ----------

@router.get("/status")
async def status():
    return {
        "now": datetime.now(timezone.utc).isoformat(),
        "times": scheduler.compute_times(),
        "next": scheduler.next_prayer(),
        "playing": player.current,
    }


# ---------- settings ----------

class Settings(BaseModel):
    lat: float
    lng: float
    method: str


@router.get("/settings")
async def get_settings():
    return {
        "lat": db.get_setting("lat"),
        "lng": db.get_setting("lng"),
        "method": db.get_setting("method", "ISNA"),
        "methods": CALC_METHODS,
    }


@router.put("/settings")
async def put_settings(s: Settings):
    if s.method not in CALC_METHODS:
        raise HTTPException(400, f"method must be one of {CALC_METHODS}")
    db.set_setting("lat", s.lat)
    db.set_setting("lng", s.lng)
    db.set_setting("method", s.method)
    await scheduler.reschedule("settings updated")
    return await get_settings()


# ---------- per-prayer config ----------

class PrayerUpdate(BaseModel):
    enabled: bool | None = None
    volume: int | None = Field(None, ge=0, le=100)
    mp3: str | None = None
    device: str | None = None


@router.get("/prayers")
async def get_prayers():
    return db.get_prayers()


@router.put("/prayers/{name}")
async def put_prayer(name: str, p: PrayerUpdate):
    if name not in PRAYER_NAMES:
        raise HTTPException(404, f"unknown prayer: {name}")
    if p.mp3 is not None and p.mp3 not in list_media():
        raise HTTPException(400, f"unknown mp3: {p.mp3}")
    db.update_prayer(name, p.model_dump(exclude_none=True))
    await scheduler.reschedule(f"{name} updated")
    return db.get_prayer(name)


# ---------- media & devices ----------

@router.get("/media")
async def media():
    return list_media()


@router.get("/devices")
async def devices():
    return await audio.list_devices()


# ---------- playback ----------

class TestRequest(BaseModel):
    mp3: str
    volume: int = Field(80, ge=0, le=100)
    device: str | None = None


@router.post("/test")
async def test_play(req: TestRequest):
    try:
        await player.play(req.mp3, req.volume, req.device, label="test")
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc))
    await emit("test", f"Test playback: {req.mp3} at volume {req.volume}")
    return {"playing": player.current}


@router.post("/stop")
async def stop_play():
    await player.stop()
    return {"playing": None}


# ---------- hooks ----------

class HookIn(BaseModel):
    name: str
    position: str = Field(pattern="^(before|after)$")
    prayers: list[str]
    days: list[int] = Field(description="0=Monday .. 6=Sunday")
    script: str
    enabled: bool = True


class HookUpdate(BaseModel):
    name: str | None = None
    position: str | None = Field(None, pattern="^(before|after)$")
    prayers: list[str] | None = None
    days: list[int] | None = None
    script: str | None = None
    enabled: bool | None = None


def _validate_hook(position: str, prayers_: list[str] | None, days: list[int] | None, script: str | None):
    if prayers_ is not None and not set(prayers_) <= set(PRAYER_NAMES):
        raise HTTPException(400, f"prayers must be a subset of {PRAYER_NAMES}")
    if days is not None and not set(days) <= set(range(7)):
        raise HTTPException(400, "days must be integers 0 (Monday) through 6 (Sunday)")
    if script is not None:
        try:
            hooks.resolve_script(position, script)
        except FileNotFoundError as exc:
            raise HTTPException(400, str(exc))


@router.get("/hooks")
async def get_hooks():
    return db.get_hooks()


@router.get("/hook-scripts")
async def hook_scripts():
    return hooks.list_scripts()


@router.post("/hooks")
async def create_hook(h: HookIn):
    _validate_hook(h.position, h.prayers, h.days, h.script)
    hook_id = db.add_hook(h.name, h.position, h.prayers, h.days, h.script, h.enabled)
    await emit("hooks", f"Added {h.position}-hook '{h.name}'")
    return {"id": hook_id}


@router.put("/hooks/{hook_id}")
async def edit_hook(hook_id: int, h: HookUpdate):
    existing = next((x for x in db.get_hooks() if x["id"] == hook_id), None)
    if not existing:
        raise HTTPException(404, "hook not found")
    position = h.position or existing["position"]
    _validate_hook(position, h.prayers, h.days, h.script if h.script else None)
    db.update_hook(hook_id, h.model_dump(exclude_none=True))
    return next(x for x in db.get_hooks() if x["id"] == hook_id)


@router.delete("/hooks/{hook_id}")
async def remove_hook(hook_id: int):
    db.delete_hook(hook_id)
    return {"ok": True}


# ---------- events & live updates ----------

@router.get("/events")
async def events(limit: int = 50):
    return db.get_events(min(limit, 500))


@router.websocket("/ws")
async def ws(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive; we only push
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
