async def sync_one_cabinet(token: str) -> dict:
    tid = token_id(token)
    db = SessionLocal()

    result = {
        "tid": tid,
        "chars_count": 0,
        "stocks_count": 0,
        "error": None
    }

    try:
        # --- ХАРАКТЕРИСТИКИ ---
        logger.info(f"Кабинет {tid}: синхронизация характеристик...")
        cards = await fetch_product_characteristics(token, nm_ids=[])
        chars_count = 0

        for card in cards:
            nm_id = card.get("nmID")
            if nm_id:
                upsert_characteristic(db, tid, nm_id, card)
                chars_count += 1

        result["chars_count"] = chars_count
        logger.info(f"Кабинет {tid}: характеристики сохранены ({chars_count})")

        # --- ОСТАТКИ ---
        logger.info(f"Кабинет {tid}: синхронизация остатков...")
        stocks = await fetch_stocks(token)
        stocks_count = 0

        for item in stocks:
            upsert_stock(db, tid, item)
            stocks_count += 1

        result["stocks_count"] = stocks_count
        logger.info(f"Кабинет {tid}: остатки сохранены ({stocks_count})")

        # --- ЛОГ ---
        log_sync(db, tid, "ok", records=chars_count + stocks_count)

        # ✅ ЕДИНЫЙ COMMIT
        db.commit()

    except Exception as e:
        logger.error(f"Ошибка кабинета {tid}: {e}")

        # ❗ откатываем всё
        db.rollback()

        result["error"] = str(e)[:200]

        try:
            # логируем ошибку в НОВОЙ транзакции
            log_sync(db, tid, "error", message=str(e)[:490])
            db.commit()
        except Exception as log_err:
            logger.error(f"Не удалось записать лог ошибки: {log_err}")

    finally:
        db.close()

    return result
