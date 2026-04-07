import httpx
import asyncio
import logging
from typing import Any
from datetime import datetime
import os
import sys

WB_BASE = "https://content-api.wildberries.ru"
WB_ANALYTICS_BASE = "https://seller-analytics-api.wildberries.ru"
logger = logging.getLogger(__name__)

# Конфигурация Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = "356741753"

async def send_telegram_message(message: str):
    """Отправка сообщения в Telegram с улучшенной обработкой ошибок"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не задан в переменных окружения")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Ограничиваем длину сообщения (Telegram лимит 4096 символов)
    if len(message) > 4000:
        message = message[:4000] + "\n\n... (сообщение обрезано)"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url, 
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML"
                }
            )
            
            if response.status_code == 200:
                logger.info("✅ Сообщение успешно отправлено в Telegram")
                return True
            else:
                logger.error(f"❌ Ошибка Telegram API: {response.status_code} - {response.text}")
                return False
                
    except httpx.TimeoutException:
        logger.error("❌ Таймаут при отправке в Telegram")
        return False
    except httpx.ConnectError:
        logger.error("❌ Не удалось подключиться к Telegram API")
        return False
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка при отправке в Telegram: {type(e).__name__}: {e}")
        return False

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

async def main():
    try:
        # Данные продавцов - ЗАМЕНИТЕ НА ВАШИ ТОКЕНЫ
        sellers = [
            {"name": "Магазин Обуви", "token": "ВАШ_ТОКЕН_ПРОДАВЦА_1", "nm_ids": []},
            {"name": "Магазин Одежды", "token": "ВАШ_ТОКЕН_ПРОДАВЦА_2", "nm_ids": []},
        ]
        
        start_time = datetime.now()
        results = []
        errors = []
        
        for seller in sellers:
            seller_result = {"name": seller["name"], "methods": {}}
            
            # Пытаемся получить характеристики
            try:
                chars = await fetch_product_characteristics(seller["token"], seller["nm_ids"])
                seller_result["methods"]["characteristics"] = f"✅ {len(chars)} карточек"
            except Exception as e:
                error_msg = f"❌ Ошибка: {str(e)[:100]}"
                seller_result["methods"]["characteristics"] = error_msg
                errors.append(f"{seller['name']} / характеристики: {e}")
            
            # Пытаемся получить остатки
            try:
                stocks = await fetch_stocks(seller["token"])
                seller_result["methods"]["stocks"] = f"✅ {len(stocks)} записей"
            except Exception as e:
                error_msg = f"❌ Ошибка: {str(e)[:100]}"
                seller_result["methods"]["stocks"] = error_msg
                errors.append(f"{seller['name']} / остатки: {e}")
            
            results.append(seller_result)
        
        # Формируем сообщение для Telegram
        duration = (datetime.now() - start_time).total_seconds()
        message = f"🔄 <b>Выгрузка данных WB</b>\n"
        message += f"⏱ Время: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"⌛️ Длительность: {duration:.1f} сек\n\n"
        
        for seller in results:
            message += f"📦 <b>{seller['name']}</b>\n"
            for method, status in seller["methods"].items():
                message += f"  • {method}: {status}\n"
            message += "\n"
        
        if errors:
            message += f"⚠️ <b>Ошибок: {len(errors)}</b>\n"
            for error in errors[:5]:
                message += f"  • {error[:80]}\n"
        else:
            message += "✅ <b>Все операции выполнены успешно!</b>"
        
        # Отправляем в Telegram
        logger.info("📤 Пытаемся отправить сообщение в Telegram...")
        success = await send_telegram_message(message)
        
        if success:
            logger.info("✅ Отчет успешно отправлен в Telegram")
        else:
            logger.warning("⚠️ Не удалось отправить отчет в Telegram, но данные сохранены")
        
        # Выводим сообщение в лог для отладки
        logger.info(f"📋 Отчет:\n{message}")
        
    except Exception as e:
        # Ловим любые ошибки, чтобы процесс завершился корректно
        logger.error(f"❌ Критическая ошибка в main: {type(e).__name__}: {e}", exc_info=True)
        
        # Пытаемся отправить сообщение об ошибке
        try:
            await send_telegram_message(f"❌ <b>Ошибка при выгрузке данных</b>\n\n{str(e)[:200]}")
        except:
            pass
        
        # Выходим с ошибкой, чтобы Render показал статус failed
        sys.exit(1)
    
    # Успешное завершение
    logger.info("✅ Скрипт выполнен успешно")
    sys.exit(0)

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запуск
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Необработанная ошибка: {e}", exc_info=True)
        sys.exit(1)
