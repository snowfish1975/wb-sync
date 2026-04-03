import httpx
from typing import Any

WB_BASE = "https://content-api.wildberries.ru"

async def fetch_product_characteristics(token: str, nm_ids: list[int]) -> list[dict[str, Any]]:
    """
    Запрашивает характеристики карточек товара.
    Документация: https://openapi.wildberries.ru/content/api/ru/#tag/Kontent/paths/~1content~1v2~1get~1cards~1list/post
    """
    headers = {"Authorization": token}
    payload = {
        "settings": {
            "cursor": {"limit": 100},
            "filter": {"withPhoto": -1},
        }
    }

    results = []
    async with httpx.AsyncClient(timeout=30) as client:
        # WB отдаёт карточки постранично — обходим все страницы
        while True:
            resp = await client.post(
                f"{WB_BASE}/content/v2/get/cards/list",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            cards = body.get("cards", [])
            results.extend(cards)

            cursor = body.get("cursor", {})
            # Если total совпадает с limit — есть ещё страницы
            if cursor.get("total", 0) < payload["settings"]["cursor"]["limit"]:
                break
            # Переходим на следующую страницу
            payload["settings"]["cursor"]["updatedAt"] = cursor["updatedAt"]
            payload["settings"]["cursor"]["nmID"] = cursor["nmID"]

    return results