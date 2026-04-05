import httpx
import asyncio
from typing import Any

WB_BASE = "https://content-api.wildberries.ru"

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
    retry_delay = 5  # секунд

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            # Повторные попытки при ошибке (как в вашем Apps Script)
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
                    if attempt == max_attempts:
                        raise RuntimeError(f"Не удалось выполнить запрос после {max_attempts} попыток: {e}")
                    await asyncio.sleep(retry_delay)

            cards = body.get("cards", [])
            results.extend(cards)

            # Если карточек меньше лимита — это последняя страница
            if len(cards) < 100:
                break

            # Передаём курсор для следующей страницы
            cursor = body.get("cursor", {})
            payload["settings"]["cursor"]["updatedAt"] = cursor["updatedAt"]
            payload["settings"]["cursor"]["nmID"] = cursor["nmID"]

    return results
