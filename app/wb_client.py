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
        # Не падаем, просто логируем
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

# ... (ваши функции fetch_product_characteristics и fetch_stocks остаются без изменений) ...

async def main():
    try:
        # Данные продавцов
        sellers = [
            {"name": "Магазин Обуви", "token": "ВАШ_ТОКЕН_1", "nm_ids": []},
            {"name": "Магазин Одежды", "token": "ВАШ_ТОКЕН_2", "nm_ids": []},
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
