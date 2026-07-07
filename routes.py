import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

import audio
import bluetooth
import db
import hijri
import hooks
import scheduler
import system
from config import (ASR_METHODS, CALC_METHODS, HIGH_LAT_RULES, MAX_UPLOAD_MB,
                    MEDIA_DIR, PRAYER_NAMES, PREFERENCE_DEFAULTS)
from events import emit, ws_manager
from player import list_media, player

router = APIRouter()


# ---------- status ----------

@router.get("/status")
async def status():
    data = scheduler.compute_times()
    ramadan = hijri.ramadan_active()
    return {
        "now": datetime.now(timezone.utc).isoformat(),
        "times": data["times"] if data else None,
        "extras": data["extras"] if data else None,
        "next": scheduler.next_prayer(),
        "playing": player.current,
        "hijri": hijri.today_hijri(),
        "ramadan_active": ramadan,
        "iftar_at": data["times"]["maghrib"] if (data and ramadan) else None,
        "mute_until": db.get_setting("mute_until") if scheduler.is_muted() else None,
        "skip_next": db.get_setting("skip_next"),
    }


# ---------- settings ----------

class Settings(BaseModel):
    lat: float
    lng: float
    method: str
    asr_method: str = "Standard"
    high_lats: str = "NightMiddle"


@router.get("/settings")
async def get_settings():
    return {
        "lat": db.get_setting("lat"),
        "lng": db.get_setting("lng"),
        "method": db.get_setting("method", "ISNA"),
        "asr_method": db.get_setting("asr_method", "Standard"),
        "high_lats": db.get_setting("high_lats", "NightMiddle"),
        "methods": CALC_METHODS,
        "asr_methods": ASR_METHODS,
        "high_lat_rules": HIGH_LAT_RULES,
    }


@router.put("/settings")
async def put_settings(s: Settings):
    if s.method not in CALC_METHODS:
        raise HTTPException(400, f"method must be one of {CALC_METHODS}")
    if s.asr_method not in ASR_METHODS:
        raise HTTPException(400, f"asr_method must be one of {ASR_METHODS}")
    if s.high_lats not in HIGH_LAT_RULES:
        raise HTTPException(400, f"high_lats must be one of {HIGH_LAT_RULES}")
    db.set_setting("lat", s.lat)
    db.set_setting("lng", s.lng)
    db.set_setting("method", s.method)
    db.set_setting("asr_method", s.asr_method)
    db.set_setting("high_lats", s.high_lats)
    await scheduler.reschedule("settings updated")
    return await get_settings()


# ---------- preferences (Ramadan, jumu'ah, fade) ----------

@router.get("/preferences")
async def get_preferences():
    return {k: db.get_setting(k, default) for k, default in PREFERENCE_DEFAULTS.items()}


@router.put("/preferences")
async def put_preferences(prefs: dict):
    unknown = set(prefs) - set(PREFERENCE_DEFAULTS)
    if unknown:
        raise HTTPException(400, f"unknown preference keys: {sorted(unknown)}")
    for key in ("suhoor_mp3", "jumuah_mp3"):
        if prefs.get(key) and prefs[key] not in list_media():
            raise HTTPException(400, f"unknown audio file for {key}: {prefs[key]}")
    if prefs.get("ramadan_mode") not in (None, "auto", "on", "off"):
        raise HTTPException(400, "ramadan_mode must be auto, on, or off")
    if prefs.get("jumuah_action") not in (None, "normal", "mp3", "skip"):
        raise HTTPException(400, "jumuah_action must be normal, mp3, or skip")
    for key, value in prefs.items():
        db.set_setting(key, value)
    await scheduler.reschedule("preferences updated")
    return await get_preferences()


# ---------- per-prayer config ----------

class PrayerUpdate(BaseModel):
    enabled: bool | None = None
    volume: int | None = Field(None, ge=0, le=100)
    mp3: str | None = None
    device: str | None = None
    offset_minutes: int | None = Field(None, ge=-60, le=60)
    reminder_minutes: int | None = Field(None, ge=0, le=120)
    dua_mp3: str | None = None


@router.get("/prayers")
async def get_prayers():
    return db.get_prayers()


@router.put("/prayers/{name}")
async def put_prayer(name: str, p: PrayerUpdate):
    if name not in PRAYER_NAMES:
        raise HTTPException(404, f"unknown prayer: {name}")
    fields = p.model_dump(exclude_none=True)
    if p.dua_mp3 == "":  # explicit clear
        fields["dua_mp3"] = None
    for key in ("mp3", "dua_mp3"):
        if fields.get(key) and fields[key] not in list_media():
            raise HTTPException(400, f"unknown audio file: {fields[key]}")
    db.update_prayer(name, fields)
    await scheduler.reschedule(f"{name} updated")
    return db.get_prayer(name)


# ---------- mute & skip ----------

class MuteRequest(BaseModel):
    until: str | None = None  # naive local ISO datetime, or null to unmute


@router.put("/mute")
async def put_mute(req: MuteRequest):
    if req.until is not None:
        try:
            until = datetime.fromisoformat(req.until)
        except ValueError:
            raise HTTPException(400, "until must be an ISO datetime or null")
        db.set_setting("mute_until", req.until)
        await emit("mute", f"Muted until {until.strftime('%a %b %d %H:%M')}")
    else:
        db.set_setting("mute_until", None)
        await emit("mute", "Unmuted")
    return {"mute_until": db.get_setting("mute_until") if scheduler.is_muted() else None}


@router.post("/skip-next")
async def skip_next():
    current = db.get_setting("skip_next")
    if current:
        db.set_setting("skip_next", None)
        await emit("mute", f"Skip for {current['name']} cancelled")
        return {"skip_next": None}
    nxt = scheduler.next_prayer()
    if not nxt:
        raise HTTPException(400, "No upcoming prayer today to skip")
    skip = {"name": nxt["name"], "date": datetime.now().date().isoformat()}
    db.set_setting("skip_next", skip)
    await emit("mute", f"Will skip the next adhan ({nxt['name']})")
    return {"skip_next": skip}


# ---------- media & devices ----------

@router.get("/media")
async def media():
    return list_media()


@router.post("/media")
async def upload_media(file: UploadFile):
    name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "")
    if not name.lower().endswith((".mp3", ".m4a")):
        raise HTTPException(400, "Only .mp3 and .m4a uploads are supported")
    if (MEDIA_DIR / name).exists():
        raise HTTPException(409, f"{name} already exists")
    limit = MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    chunks = []
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")
        chunks.append(chunk)
    if size == 0:
        raise HTTPException(400, "Empty file")
    (MEDIA_DIR / name).write_bytes(b"".join(chunks))
    await emit("media", f"Uploaded {name} ({size // 1024} KB)")
    return {"name": name, "media": list_media()}


@router.get("/devices")
async def devices():
    return await audio.list_devices()


# ---------- playback ----------

class TestRequest(BaseModel):
    mp3: str
    volume: int = Field(80, ge=0, le=100)
    device: str | None = None
    duration: int | None = Field(None, ge=1, le=60)  # preview cap in seconds


@router.post("/test")
async def test_play(req: TestRequest):
    label = "preview" if req.duration else "test"
    try:
        await player.play(req.mp3, req.volume, req.device, label=label, duration=req.duration)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc))
    if not req.duration:
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


# ---------- Bluetooth speakers ----------

class BtRequest(BaseModel):
    mac: str


@router.get("/bluetooth")
async def bt_status():
    return await bluetooth.status()


@router.post("/bluetooth/scan")
async def bt_scan():
    if not bluetooth.available():
        raise HTTPException(400, "bluetoothctl not available on this machine")
    return await bluetooth.scan()


@router.post("/bluetooth/{action}")
async def bt_action(action: str, req: BtRequest):
    if not bluetooth.available():
        raise HTTPException(400, "bluetoothctl not available on this machine")
    handlers = {"pair": bluetooth.pair, "connect": bluetooth.connect,
                "disconnect": bluetooth.disconnect, "forget": bluetooth.forget}
    if action not in handlers:
        raise HTTPException(404, f"unknown action: {action}")
    try:
        output = await handlers[action](req.mac)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))
    await emit("bluetooth", f"{action} {req.mac}")
    return {"ok": True, "output": output[-500:]}


# ---------- health & self-update ----------

@router.get("/health")
async def health():
    return system.health()


@router.post("/update")
async def update():
    result = await system.self_update()
    await emit("system", "Update: " + (result["output"].splitlines()[-1] if result["output"] else "done"))
    return result


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
