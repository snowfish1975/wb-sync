import httpx
import asyncio
import logging
from typing import Any

WB_BASE = "https://content-api.wildberries.ru"
logger = logging.getLogger(__name__)

async def fetch_product_characteristics(token: str, nm_ids: list[int]) -> list[dict[str, Any]]:
    headers = {"Authorization": token}
    payload = {
        "settings": {
            "filter": {"withPhoto": -1},
            "cursor": {"limit": 100},
        }
    }

    results = []
    max_attempts = 10
    retry_delay = 5
    page = 1

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            logger.info(f"Запрос страницы {page}, payload cursor: {payload['settings']['cursor']}")

            for attempt in range(1, max_attempts + 1):
                try:
                    resp = await client.post(
                        f"{WB_BASE}/content/v2/get/cards/list",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    body = resp.json()
                    break
                except Exception as e:
                    logger.warning(f"Попытка {attempt}/{max_attempts} неудачна: {e}")
                    if attempt == max_attempts:
                        raise RuntimeError(f"Не удалось выполнить запрос после {max_attempts} попыток: {e}")
                    await asyncio.sleep(retry_delay)

            cards = body.get("cards", [])
            cursor = body.get("cursor", {})

            logger.info(f"Страница {page}: получено {len(cards)} карточек, cursor в ответе: {cursor}")
            logger.info(f"Итого накоплено: {len(results) + len(cards)}")

            results.extend(cards)

            if len(cards) < 100:
                logger.info(f"Последняя страница (получено {len(cards)} < 100), завершаем.")
                break

            if not cursor.get("updatedAt") or not cursor.get("nmID"):
                logger.warning(f"Курсор пустой или неполный, завершаем: {cursor}")
                break

            payload["settings"]["cursor"]["updatedAt"] = cursor["updatedAt"]
            payload["settings"]["cursor"]["nmID"] = cursor["nmID"]
            page += 1

    logger.info(f"Всего получено карточек: {len(results)}")
    return results
