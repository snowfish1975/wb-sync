import os
import asyncio
import hashlib
import logging
import httpx
from datetime import datetime

from app.wb_client import fetch_product_characteristics, fetch_stocks
from app.crud import upsert_characteristic, upsert_stock, log_sync
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "356741753")


# --- TOKENS + NAMES ---
def get_token_mapping() -> dict[str, str]:
    """
    Возвращает:
    {
        cabinet_id: "Имя продавца"
    }
    """
    tokens = [t.strip() for t in os.getenv("WB_TOKENS", "").split(",") if t.strip()]
    names = [n.strip() for n in os.getenv("WB_NAMES", "").split(",") if n.strip()]

    mapping = {}

    for i, token in enumerate(tokens):
        tid = token_id(token)
        name = names[i] if i < len(names) else tid[:8]  # fallback
        mapping[tid] = name

    return mapping


def get_tokens() -> list[str]:
    raw = os.getenv("WB_TOKENS", "")
    return [t.strip() for t in raw.split(",") if t.strip()]


def token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:32]


async def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN не задан, сообщение не отправлено")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
            if response.status_code == 200:
                logger.info("✅ Сообщение отправлено в Telegram")
            else:
                logger.error(f"❌ Ошибка Telegram: {response.text}")
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение: {e}")


# --- SYNC ONE ---
async def sync_one_cabinet(token: str, name: str) -> dict:
    tid = token_id(token)
    db = SessionLocal()

    result = {
        "tid": tid,
        "name": name,
        "chars_count": 0,
        "stocks_count": 0,
        "error": None,
    }

    try:
        logger.info(f"[{name}] синхронизация характеристик...")
        cards = await fetch_product_characteristics(token, nm_ids=[])
        chars_count = 0

        for card in cards:
            nm_id = card.get("nmID")
            if nm_id:
                upsert_characteristic(db, tid, nm_id, card)
                chars_count += 1

        result["chars_count"] = chars_count
        logger.info(f"[{name}] характеристики сохранены ({chars_count})")

        logger.info(f"[{name}] синхронизация остатков...")
        stocks = await fetch_stocks(token)
        stocks_count = 0

        for item in stocks:
            upsert_stock(db, tid, item)
            stocks_count += 1

        result["stocks_count"] = stocks_count
        logger.info(f"[{name}] остатки сохранены ({stocks_count})")

        log_sync(db, tid, "ok", records=chars_count + stocks_count)

        db.commit()

    except Exception as e:
        logger.error(f"[{name}] ошибка: {e}")

        db.rollback()
        result["error"] = str(e)[:200]

        try:
            log_sync(db, tid, "error", message=str(e)[:490])
            db.commit()
        except Exception as log_err:
            logger.error(f"[{name}] не удалось записать лог: {log_err}")

    finally:
        db.close()

    return result


# --- RUN ALL ---
def run_sync_all():
    tokens = get_tokens()
    mapping = get_token_mapping()

    if not tokens:
        logger.warning("WB_TOKENS не заданы, пропускаю синхронизацию")
        return

    async def _run():
        start_time = datetime.now()

        tasks = []
        for token in tokens:
            tid = token_id(token)
            name = mapping.get(tid, tid[:8])
            tasks.append(sync_one_cabinet(token, name))

        results = await asyncio.gather(*tasks)

        duration = (datetime.now() - start_time).total_seconds()

        # --- Telegram ---
        message = f"🔄 <b>Выгрузка данных WB</b>\n"
        message += f"⏱ Время: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"⌛️ Длительность: {duration:.1f} сек\n\n"

        success_count = 0
        error_count = 0

        for r in results:
            if r["error"]:
                error_count += 1
                message += f"❌ <b>{r['name']}</b>\n"
                message += f"   Ошибка: {r['error'][:100]}\n\n"
            else:
                success_count += 1
                message += f"✅ <b>{r['name']}</b>\n"
                message += f"   • Характеристики: {r['chars_count']}\n"
                message += f"   • Остатки: {r['stocks_count']}\n\n"

        message += f"📊 <b>Итог:</b> успешно: {success_count}, ошибок: {error_count}"

        await send_telegram_message(message)
        logger.info(f"\n{message}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()