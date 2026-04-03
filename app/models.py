from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class ProductCharacteristic(Base):
    """Характеристики товара — один метод WB API."""
    __tablename__ = "product_characteristics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cabinet_token_hint: Mapped[str] = mapped_column(String(20))  # первые 8 символов токена
    nm_id: Mapped[int] = mapped_column(Integer)                   # артикул WB
    characteristics: Mapped[dict] = mapped_column(JSON)           # сырой ответ API
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("cabinet_token_hint", "nm_id", name="uq_cabinet_nm"),
    )

class SyncLog(Base):
    """Лог каждой синхронизации."""
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cabinet_token_hint: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))   # ok / error
    message: Mapped[str] = mapped_column(String(500), nullable=True)
    records_saved: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)