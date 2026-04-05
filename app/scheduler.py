import os
import asyncio
import hashlib
import logging
from app.wb_client import fetch_product_characteristics
from app.crud import upsert_characteristic, log_sync
from app.database import SessionLocal

logger = logging.getLogger(__name__)

def get_tokens() -> list[str]:
    raw = os.getenv("WB_TOKENS", "")
    return [t.strip() for t in raw.split(",") if t.strip()]

def token_id(token: str) -> str:
    """SHA-256 хэш токена — уникальный идентификатор кабинета."""
    return hashlib.sha256(token.encode()).hexdigest()[:32]

async def sync_one_cabinet(token: str):
    tid = token_id(token)
    db = SessionLocal()
    try:
        logger.info(f"Синхронизация кабинета {tid}...")
        cards = await fetch_product_characteristics(token, nm_ids=[])
        count = 0
        for card in cards:
            nm_id = card.get("nmID")
            if nm_id:
                upsert_characteristic(db, tid, nm_id, card)
                count += 1
        log_sync(db, tid, "ok", records=count)
        logger.info(f"Кабинет {tid}: сохранено {count} записей")
    except Exception as e:
        log_sync(db, tid, "error", message=str(e)[:490])
        logger.error(f"Ошибка кабинета {tid}: {e}")
    finally:
        db.close()

def run_sync_all():
    tokens = get_tokens()
    if not tokens:
        logger.warning("WB_TOKENS не заданы, пропускаю синхронизацию")
        return

    async def _run():
        await asyncio.gather(*[sync_one_cabinet(t) for t in tokens])

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()