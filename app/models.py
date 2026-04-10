from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, UniqueConstraint, Float, Boolean, BigInteger
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


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cabinet_id: Mapped[str] = mapped_column(String(32))
    nm_id: Mapped[int] = mapped_column(Integer)
    chrt_id: Mapped[int] = mapped_column(Integer)
    warehouse_id: Mapped[int] = mapped_column(Integer)
    warehouse_name: Mapped[str] = mapped_column(String(200))
    region_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    in_way_to_client: Mapped[int] = mapped_column(Integer)
    in_way_from_client: Mapped[int] = mapped_column(Integer)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("cabinet_id", "chrt_id", "warehouse_id", name="uq_stock"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cabinet_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    
    # Основные поля заказа
    srid: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Уникальный ID заказа
    g_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)  # ID корзины
    nm_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    supplier_article: Mapped[str] = mapped_column(String(75), nullable=True)
    barcode: Mapped[str] = mapped_column(String(30), nullable=True)
    
    # Информация о заказе
    date: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # Дата и время заказа (создания)
    last_change_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # Дата последнего изменения
    cancel_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # Дата отмены
    
    # Цены
    total_price: Mapped[float] = mapped_column(Float, nullable=True)
    finished_price: Mapped[float] = mapped_column(Float, nullable=True)
    price_with_disc: Mapped[float] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=True)
    spp: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Статусы
    is_cancel: Mapped[bool] = mapped_column(Boolean, default=False)
    is_supply: Mapped[bool] = mapped_column(Boolean, default=False)
    is_realization: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Дополнительная информация
    warehouse_name: Mapped[str] = mapped_column(String(50), nullable=True)
    warehouse_type: Mapped[str] = mapped_column(String(50), nullable=True)
    country_name: Mapped[str] = mapped_column(String(200), nullable=True)
    region_name: Mapped[str] = mapped_column(String(200), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=True)
    subject: Mapped[str] = mapped_column(String(50), nullable=True)
    brand: Mapped[str] = mapped_column(String(50), nullable=True)
    tech_size: Mapped[str] = mapped_column(String(30), nullable=True)
    sticker: Mapped[str] = mapped_column(String(50), nullable=True)
    income_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    
    # Служебные поля
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("cabinet_id", "srid", name="uq_cabinet_order"),
    )


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cabinet_id: Mapped[str] = mapped_column(String(32))
    nm_id: Mapped[int] = mapped_column(Integer)
    chrt_id: Mapped[int] = mapped_column(Integer)

    price: Mapped[int] = mapped_column(Integer)
    discounted_price: Mapped[float] = mapped_column(Float)
    club_discounted_price: Mapped[float] = mapped_column(Float)

    currency: Mapped[str] = mapped_column(String(10))

    discount: Mapped[int] = mapped_column(Integer)
    club_discount: Mapped[int] = mapped_column(Integer)

    tech_size_name: Mapped[str] = mapped_column(String(50))

    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("cabinet_id", "chrt_id", name="uq_price"),
    )
