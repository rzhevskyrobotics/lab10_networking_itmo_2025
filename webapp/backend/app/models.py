from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class HttpHit(Base):
    __tablename__ = "http_hits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str | None] = mapped_column(String(80), index=True)
    host: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(255))
    ip: Mapped[str] = mapped_column(String(45), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

Index("ix_http_hits_created", HttpHit.created_at.desc())

class DnsHit(Base):
    __tablename__ = "dns_hits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str | None] = mapped_column(String(80), index=True)
    qname: Mapped[str] = mapped_column(String(255))
    resolver_ip: Mapped[str] = mapped_column(String(45), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

Index("ix_dns_hits_created", DnsHit.created_at.desc())

# --- лог пингов по токену ---
class TokenHit(Base):
    __tablename__ = "token_hits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(80), index=True)
    ip: Mapped[str] = mapped_column(String(45), index=True)        # IPv4/IPv6
    asn: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    as_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

Index("ix_token_hits_created", TokenHit.created_at.desc())
