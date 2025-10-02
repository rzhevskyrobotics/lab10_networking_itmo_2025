import re
import asyncio
import uuid
from typing import AsyncGenerator, List, Optional
import os, time, shutil, urllib.request, asyncio

from fastapi import FastAPI, Depends, HTTPException, Request, File
from fastapi.responses import StreamingResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .settings import BASE_DOMAIN, RIPE_URL, DATA_DIR
from .db import SessionLocal, init_db
from .models import HttpHit, DnsHit, Item, TokenHit
from .asn_lookup import ip_to_asn

RIPE_LOCAL = os.path.join(DATA_DIR, "delegated-ripencc-latest")

app = FastAPI(title="Async Demo: Progress + REST + SQLite")

# Разрешим CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

def _file_age_seconds(path: str) -> float:
    return time.time() - os.path.getmtime(path)

# -----------------------------
# Схемы (Pydantic)
# -----------------------------
class ItemIn(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None

class ItemPatch(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None

    # запретим пустой PATCH без полей
    def model_post_init(self, __context):
        if self.title is None and self.description is None:
            raise ValueError("At least one field must be provided")

class ItemOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    created_at: str

class PingIn(BaseModel):
    token: str = Field(..., min_length=1, max_length=80)

class PingOut(BaseModel):
    token: str
    ip: str
    asn: int | None = None
    as_name: str | None = None
    prefix: str | None = None
    duplicate: bool = False

class PingRow(BaseModel):
    when: str
    token: str
    ip: str
    asn: int | None = None
    as_name: str | None = None
    prefix: str | None = None
    user_agent: str | None = None

class StatRow(BaseModel):
    asn: int | None
    as_name: str | None
    count: int

class PingStatsOut(BaseModel):
    total_hits: int
    unique_ips: int
    top: list[StatRow]

# -----------------------------
# Инициализация БД при старте
# -----------------------------
@app.on_event("startup")
async def on_startup():
    await init_db()
    os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------
# Статика (демо страница)
# -----------------------------
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("static/index.html")

# -----------------------------
# CRUD по REST для таблицы items
# -----------------------------
@app.post("/api/items", response_model=ItemOut, status_code=201)
async def create_item(payload: ItemIn, db: AsyncSession = Depends(get_db)):
    item = Item(title=payload.title, description=payload.description)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ItemOut(
        id=item.id,
        title=item.title,
        description=item.description,
        created_at=item.created_at.isoformat()
    )

@app.get("/api/items", response_model=List[ItemOut])
async def list_items(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Item).order_by(Item.id.desc()))
    items = res.scalars().all()
    return [
        ItemOut(
            id=i.id,
            title=i.title,
            description=i.description,
            created_at=i.created_at.isoformat()
        ) for i in items
    ]

@app.put("/api/items/{item_id}", response_model=ItemOut)
async def update_item(item_id: int, payload: ItemIn, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Item).where(Item.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Item not found")

    item.title = payload.title
    item.description = payload.description
    await db.commit()
    await db.refresh(item)

    return ItemOut(
        id=item.id,
        title=item.title,
        description=item.description,
        created_at=item.created_at.isoformat()
    )

@app.patch("/api/items/{item_id}", response_model=ItemOut)
async def patch_item(item_id: int, payload: ItemPatch, db: AsyncSession = Depends(get_db)):
    # pydantic v2: исключим None-поля
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "Empty patch")

    res = await db.execute(select(Item).where(Item.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Item not found")

    # Применяем только присланные поля
    for k, v in updates.items():
        setattr(item, k, v)

    await db.commit()
    await db.refresh(item)

    return ItemOut(
        id=item.id,
        title=item.title,
        description=item.description,
        created_at=item.created_at.isoformat()
    )

@app.delete("/api/items/{item_id}", status_code=204)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Item).where(Item.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Item not found")
    await db.delete(item)
    await db.commit()
    return None

@app.post("/api/ripe/ensure")
async def ripe_ensure(force: bool = False, max_age_hours: int = 24):
    os.makedirs(DATA_DIR, exist_ok=True)
    need = force or (not os.path.exists(RIPE_LOCAL)) or (_file_age_seconds(RIPE_LOCAL) > max_age_hours * 3600)

    downloaded = False
    if need:
        tmp = RIPE_LOCAL + ".tmp"
        def _download():
            with urllib.request.urlopen(RIPE_URL) as resp, open(tmp, "wb") as out:
                shutil.copyfileobj(resp, out)
            os.replace(tmp, RIPE_LOCAL)
        await asyncio.to_thread(_download)
        downloaded = True

    size  = os.path.getsize(RIPE_LOCAL) if os.path.exists(RIPE_LOCAL) else 0
    mtime = os.path.getmtime(RIPE_LOCAL) if os.path.exists(RIPE_LOCAL) else None
    return {"downloaded": downloaded, "size": size, "mtime": mtime}

# Отдаём кэшированный файл
@app.get("/api/ripe/file")
async def ripe_file():
    if not os.path.exists(RIPE_LOCAL):
        raise HTTPException(404, "RIPE file not found; POST /api/ripe/ensure first")
    # FileResponse отдаёт Content-Length → фронту будет что показывать в прогрессе
    return FileResponse(RIPE_LOCAL, media_type="text/plain", filename="delegated-ripencc-latest")

# POST /api/ping
@app.post("/api/ping", response_model=PingOut)
async def ping(payload: PingIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")[:255]

    # быстрый софт-чек (а хард-чек — уникальный индекс)
    exists = await db.execute(select(TokenHit.id).where(TokenHit.ip == ip).limit(1))
    if exists.scalar_one_or_none() is not None:
        # ASN всё равно попробуем определить и показать пользователю актуальные данные
        asn = as_name = prefix = None
        try:
            res = await ip_to_asn(ip)
            best = res.get("best") or {}
            asn, as_name, prefix = best.get("asn"), best.get("as_name"), best.get("prefix")
        except Exception:
            pass
        return PingOut(token=payload.token, ip=ip, asn=asn, as_name=as_name, prefix=prefix, duplicate=True)

    # обогащение ASN
    asn = as_name = prefix = None
    try:
        res = await ip_to_asn(ip)
        best = res.get("best") or {}
        asn, as_name, prefix = best.get("asn"), best.get("as_name"), best.get("prefix")
    except Exception:
        pass

    # запись; ловим IntegrityError, если два запроса пришли одновременно
    try:
        db.add(TokenHit(token=payload.token, ip=ip, asn=asn, as_name=as_name, prefix=prefix, user_agent=ua))
        await db.commit()
        return PingOut(token=payload.token, ip=ip, asn=asn, as_name=as_name, prefix=prefix, duplicate=False)
    except IntegrityError:
        # второй запрос промахнулся в уникальный индекс — считаем дубликатом
        await db.rollback()
        return PingOut(token=payload.token, ip=ip, asn=asn, as_name=as_name, prefix=prefix, duplicate=True)

# GET /api/ping/stats — всего, уникальные IP и ТОП-5 ASN
@app.get("/api/ping/stats", response_model=PingStatsOut)
async def ping_stats(db: AsyncSession = Depends(get_db), top: int = 5):
    total = (await db.execute(select(func.count(TokenHit.id)))).scalar_one()
    uniq  = (await db.execute(select(func.count(func.distinct(TokenHit.ip))))).scalar_one()

    agg = await db.execute(
        select(TokenHit.asn, TokenHit.as_name, func.count().label("cnt"))
        .group_by(TokenHit.asn, TokenHit.as_name)
        .order_by(desc("cnt"))
        .limit(top)
    )
    top_rows = [StatRow(asn=a, as_name=n, count=int(c)) for a, n, c in agg.all()]
    return PingStatsOut(total_hits=int(total), unique_ips=int(uniq), top=top_rows)

# GET /api/ping/last — последние N пингов (список “пользователей”)
@app.get("/api/ping/last", response_model=list[PingRow])
async def ping_last(db: AsyncSession = Depends(get_db), limit: int = 100):
    q = await db.execute(select(TokenHit).order_by(TokenHit.created_at.desc()).limit(limit))
    rows = q.scalars().all()
    return [
        PingRow(
            when=r.created_at.isoformat(timespec="seconds"),
            token=r.token, ip=r.ip, asn=r.asn, as_name=r.as_name, prefix=r.prefix,
            user_agent=r.user_agent
        )
        for r in rows
    ]

@app.post("/api/ping/clear")
async def ping_clear(db: AsyncSession = Depends(get_db)):
    before = (await db.execute(select(func.count(TokenHit.id)))).scalar_one()
    await db.execute(delete(TokenHit))
    await db.commit()
    return {"deleted": int(before)}

def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    return xff.split(",")[0].strip() if xff else request.client.host

def extract_token_from_host(host: str) -> str | None:
    host = host.split(":")[0].lower()
    if host.endswith("." + BASE_DOMAIN):
        return host[:-(len(BASE_DOMAIN)+1)].split(".")[0] or None
    return None
