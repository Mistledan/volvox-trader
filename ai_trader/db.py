"""Database: models + session management for the multi-user SaaS backend.

Two engines work interchangeably:
- default  : sqlite:///data/volvox.sqlite3 (zero-setup local dev)
- production: DATABASE_URL=postgresql+psycopg2://...  (deployed host)
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(260))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)

    accounts: Mapped[list["Account"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tokens: Mapped[list["ApiToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    last_used_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="tokens")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), default="paper")
    initial_balance: Mapped[float] = mapped_column(Float, default=10000.0)
    cash_usd: Mapped[float] = mapped_column(Float, default=10000.0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)

    user: Mapped[User] = relationship(back_populates="accounts")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    trades: Mapped[list["TradeRecord"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    decisions: Mapped[list["DecisionRecord"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("account_id", "symbol", name="uq_holding_account_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    opened_at: Mapped[float] = mapped_column(Float, default=time.time)

    account: Mapped[Account] = relationship(back_populates="holdings")


class TradeRecord(Base):
    __tablename__ = "trade_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(String(1000), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[float] = mapped_column(Float, default=time.time, index=True)

    account: Mapped[Account] = relationship(back_populates="trades")


class DecisionRecord(Base):
    __tablename__ = "decision_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(16))
    symbol: Mapped[str] = mapped_column(String(32), default="none")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    size: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(32), default="noop")
    timestamp: Mapped[float] = mapped_column(Float, default=time.time, index=True)

    account: Mapped[Account] = relationship(back_populates="decisions")


_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def get_db_url() -> str:
    return os.getenv("DATABASE_URL") or f"sqlite:///{PROJECT_ROOT / 'data' / 'volvox.sqlite3'}"


def init_db(url: str | None = None) -> Engine:
    global _engine, _session_factory
    db_url = url or get_db_url()
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    _engine = create_engine(db_url, connect_args=connect_args)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    if db_url.startswith("sqlite"):
        Path(db_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(_engine)
    return _engine


def session_factory() -> sessionmaker:
    if _session_factory is None:
        init_db()
    return _session_factory  # type: ignore[return-value]


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()