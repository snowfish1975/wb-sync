import os
import asyncio
import logging
from app.wb_client import fetch_product_characteristics
from app.crud import upsert_characteristic, log_sync
from app.database import SessionLocal

logger = logging.getLogger(__name__)

def get_tokens() -> list[str]:
    raw = os.getenv("WB_TOKENS", "")
    return [t.strip() for t in raw.split(",") if t.strip()]

def token_hint(token: str) -> str:
    """Первые 8 символов токена — для логов и фильтрации (не секрет)."""
    return token[:8]

async def sync_one_cabinet(token: str):
    hint = token_hint(token)
    db = SessionLocal()
    try:
        logger.info(f"Синхронизация кабинета {hint}...")
        cards = await fetch_product_characteristics(token, nm_ids=[])
        count = 0
        for card in cards:
            nm_id = card.get("nmID")
            if nm_id:
                upsert_characteristic(db, hint, nm_id, card)
                count += 1
        log_sync(db, hint, "ok", records=count)
        logger.info(f"Кабинет {hint}: сохранено {count} записей")
    except Exception as e:
        log_sync(db, hint, "error", message=str(e)[:490])
        logger.error(f"Ошибка кабинета {hint}: {e}")
    finally:
        db.close()

def run_sync_all():
    """Синхронный враппер — вызывается планировщиком."""
    tokens = get_tokens()
    if not tokens:
        logger.warning("WB_TOKENS не заданы, пропускаю синхронизацию")
        return
    asyncio.run(asyncio.gather(*[sync_one_cabinet(t) for t in tokens]))