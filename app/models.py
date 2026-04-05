from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class ProductCharacteristic(Base):
    __tablename__ = "product_characteristics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cabinet_id: Mapped[str] = mapped_column(String(32))  # SHA-256 хэш токена
    nm_id: Mapped[int] = mapped_column(Integer)
    characteristics: Mapped[dict] = mapped_column(JSON)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("cabinet_id", "nm_id", name="uq_cabinet_nm"),
    )

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cabinet_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(500), nullable=True)
    records_saved: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)