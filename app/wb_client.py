import httpx
import asyncio
import logging
from typing import Any
from datetime import datetime, timedelta, timezone

WB_BASE = "https://content-api.wildberries.ru"
WB_ANALYTICS_BASE = "https://seller-analytics-api.wildberries.ru"
WB_STATS_BASE = "https://statistics-api.wildberries.ru"
logger = logging.getLogger(__name__)

# Московский часовой пояс (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))


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

    while True:
        logger.info(f"Запрос страницы {page}, payload cursor: {payload['settings']['cursor']}")

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{WB_BASE}/content/v2/get/cards/list",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    body = resp.json()
                    logger.info(f"Характеристики, попытка {attempt} успешна: HTTP 200")
                    break
            except Exception as e:
                logger.warning(f"Характеристики, попытка {attempt}/{max_attempts} неудачна: {type(e).__name__}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.warning(f"HTTP статус: {e.response.status_code}, тело: {e.response.text[:500]}")
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

    logger.info(f"Характеристики: всего получено {len(results)} карточек за {page} страниц")
    return results


async def fetch_stocks(token: str) -> list[dict[str, Any]]:
    """
    Остатки на складах WB.
    Лимит: 3 запроса в минуту, интервал 20 сек.
    Пагинация через offset.
    """
    headers = {"Authorization": token}
    limit = 250000
    offset = 0
    results = []

    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            payload = {
                "nmIds": [],
                "limit": limit,
                "offset": offset,
            }

            for attempt in range(1, 11):
                try:
                    resp = await client.post(
                        f"{WB_ANALYTICS_BASE}/api/analytics/v1/stocks-report/wb-warehouses",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    body = resp.json()
                    break
                except Exception as e:
                    logger.warning(f"Остатки, попытка {attempt}/10: {type(e).__name__}: {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        logger.warning(f"HTTP статус: {e.response.status_code}, тело: {e.response.text[:500]}")
                    if attempt == 10:
                        raise RuntimeError(f"Не удалось получить остатки: {e}")
                    await asyncio.sleep(20)

            items = body.get("data", {}).get("items", [])
            logger.info(f"Остатки: получено {len(items)} строк, offset={offset}")
            results.extend(items)

            if len(items) < limit:
                break

            offset += limit

    logger.info(f"Остатки: всего получено {len(results)} строк")
    return results


async def fetch_orders(token: str, date_from: datetime | None = None, flag: int = 0) -> list[dict[str, Any]]:
    """
    Получение заказов за период.
    
    Args:
        token: Токен продавца
        date_from: Дата начала (в московском времени). Если None - последние 40 дней
        flag: 0 - по дате изменения, 1 - по дате создания
    
    Returns:
        Список заказов
    """
    headers = {"Authorization": token}
    
    # Если дата не указана, берем последние 40 дней от текущего момента (Москва)
    if date_from is None:
        now_moscow = datetime.now(MOSCOW_TZ)
        date_from = now_moscow - timedelta(days=40)
    
    # Форматируем дату в формате RFC3339 с московским временем
    date_from_str = date_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    results = []
    max_attempts = 5
    retry_delay = 30  # 30 секунд между попытками (учитывая лимит 1 запрос в минуту)
    current_date_from = date_from_str
    
    while True:
        logger.info(f"Запрос заказов с dateFrom={current_date_from}, flag={flag}")
        
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.get(
                        f"{WB_STATS_BASE}/api/v1/supplier/orders",
                        headers=headers,
                        params={
                            "dateFrom": current_date_from,
                            "flag": flag
                        }
                    )
                    response.raise_for_status()
                    orders = response.json()
                    logger.info(f"Заказы, попытка {attempt} успешна: HTTP 200, получено {len(orders)} записей")
                    break
            except Exception as e:
                logger.warning(f"Заказы, попытка {attempt}/{max_attempts} неудачна: {type(e).__name__}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.warning(f"HTTP статус: {e.response.status_code}, тело: {e.response.text[:500]}")
                if attempt == max_attempts:
                    raise RuntimeError(f"Не удалось получить заказы после {max_attempts} попыток: {e}")
                await asyncio.sleep(retry_delay)
        
        if not orders:
            logger.info("Заказы: получен пустой массив, завершаем выгрузку")
            break
        
        results.extend(orders)
        
        # Если получили меньше 80000, значит это последняя страница
        if len(orders) < 80000:
            logger.info(f"Заказы: получено {len(orders)} < 80000, завершаем")
            break
        
        # Для следующей страницы используем lastChangeDate из последнего заказа
        last_order = orders[-1]
        current_date_from = last_order.get("lastChangeDate")
        if not current_date_from:
            logger.warning("Заказы: нет lastChangeDate в последнем заказе, завершаем")
            break
        
        logger.info(f"Заказы: продолжаем с dateFrom={current_date_from}")
    
    logger.info(f"Заказы: всего получено {len(results)} записей")
    return results


async def fetch_orders_last_40_days(token: str) -> list[dict[str, Any]]:
    """
    Получение заказов за последние 40 дней с фильтрацией по дате создания.
    
    Из-за особенностей API с flag=0 (по lastChangeDate) получаем заказы,
    которые менялись за последние 40 дней, но среди них могут быть старые заказы.
    Фильтруем их по дате создания (date).
    """
    # Получаем заказы за последние 40 дней по дате изменения
    orders = await fetch_orders(token, flag=0)
    
    # Вычисляем пороговую дату (40 дней назад от сегодня в Москве)
    now_moscow = datetime.now(MOSCOW_TZ)
    today_start = now_moscow.replace(hour=0, minute=0, second=0, microsecond=0)
    threshold_date = today_start - timedelta(days=40)  # 40 дней назад от начала сегодня
    threshold_date_str = threshold_date.strftime("%Y-%m-%d")  # ← добавьте эту строку
    tomorrow_start = today_start + timedelta(days=1)   # начало следующего дня (для фильтрации)
    
    logger.info(f"Пороговая дата для фильтрации заказов: {threshold_date_str}")
    logger.info(f"Исключаем заказы от: {today_start.strftime('%Y-%m-%d')} и позже")
    
    # Фильтруем заказы: оставляем только созданные за последние 40 дней
    filtered_orders = []
    filtered_out_count = 0
    
    for order in orders:
        # Получаем дату создания заказа
        order_date_str = order.get("date")
        if not order_date_str:
            filtered_out_count += 1
            continue
        
        # Парсим дату заказа (она уже в московском времени)
        try:
            # Обрезаем время, сравниваем только даты
            order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
            # Конвертируем в московское время для сравнения
            order_date_moscow = order_date.astimezone(MOSCOW_TZ)
            order_date_only = order_date_moscow.date()
            threshold_date_only = threshold_date.date()
            
            if order_date_only >= threshold_date_only and order_date_only < today_start.date():
                filtered_orders.append(order)
            else:
                filtered_out_count += 1
                logger.debug(f"Отфильтрован старый заказ: дата {order_date_only}, NMID {order.get('nmId')}")
        except Exception as e:
            logger.warning(f"Ошибка парсинга даты заказа {order_date_str}: {e}")
            filtered_out_count += 1
    
    logger.info(f"Заказы: после фильтрации осталось {len(filtered_orders)} из {len(orders)} (отфильтровано {filtered_out_count})")
    
    return filtered_orders
