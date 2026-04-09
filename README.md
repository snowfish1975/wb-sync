# WB Sync

Сервис синхронизации данных Wildberries.

Приложение регулярно загружает данные из API Wildberries (характеристики товаров и остатки),
сохраняет их в PostgreSQL и предоставляет доступ через REST API.

---

## 🚀 Возможности

- Поддержка нескольких кабинетов продавцов
- Привязка токенов к **человекочитаемым именам продавцов**
- Ежедневная автоматическая синхронизация (cron)
- Ручной запуск синхронизации через API
- Хранение истории синхронизаций (логов)
- Получение данных через REST API
- Отправка отчётов в Telegram

---

## 📦 Что синхронизируется

- ✅ Характеристики товаров (cards/list)
- ✅ Остатки на складах (stocks)

---

## 🧱 Архитектура

```

WB API → scheduler → PostgreSQL → FastAPI → клиент

````

- `scheduler.py` — синхронизация и Telegram отчёты
- `crud.py` — работа с БД (без commit)
- `main.py` — API
- `wb_client.py` — работа с API Wildberries

---

## ⚙️ Технологии

- Python 3.11
- FastAPI
- SQLAlchemy
- PostgreSQL
- APScheduler
- httpx
- Render.com (деплой)

---

## 🛠 Локальный запуск

### 1. Клонировать репозиторий

```bash
git clone https://github.com/ВАШ_ЛОГИН/wb-sync.git
cd wb-sync
````

---

### 2. Виртуальное окружение

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

---

### 3. Настройка `.env`

```bash
cp .env.example .env
```

### Пример:

```env
DATABASE_URL=postgresql://user:password@localhost/wb_sync

# Новый формат (рекомендуется)
WB_TOKENS_JSON={"ИП Иванов":"token1","ООО Ромашка":"token2"}

SYNC_HOUR=3

TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=123456
```

---

## 🔐 Работа с токенами (ВАЖНО)

Теперь используется формат:

```env
WB_TOKENS_JSON={"Имя продавца":"API_TOKEN"}
```

### Пример:

```env
WB_TOKENS_JSON={
  "ИП Иванов":"abcdef123...",
  "ООО Ромашка":"987654..."
}
```

### Преимущества:

* не нужно соблюдать порядок токенов
* легко добавлять/удалять
* удобно читать и редактировать
* сразу есть имя продавца для логов и API

---

## ▶️ Запуск

```bash
uvicorn app.main:app --reload
```

Swagger:

```
http://localhost:8000/docs
```

---

## 📡 API

### 🔹 Получить товары

```http
POST /api/products
```

Body:

```json
{
  "token": "API_TOKEN"
}
```

---

### 🔹 Получить остатки

```http
POST /api/stocks
```

---

### 🔹 Получить логи синхронизации

```http
GET /api/logs
```

---

### 🔹 Запустить синхронизацию вручную

```http
POST /api/sync/trigger
```

---

## 📊 Формат ответа API

Теперь возвращается:

```json
{
  "nm_id": 123456,
  "seller_name": "ИП Иванов",
  "quantity": 10
}
```

👉 `seller_name` подставляется автоматически из `.env`

---

## ⏱ Планировщик

Используется APScheduler.

```env
SYNC_HOUR=3
```

→ запуск каждый день в 03:00 UTC

---

## 📩 Telegram уведомления

После каждой синхронизации отправляется отчёт:

* количество обработанных записей
* ошибки по кабинетам
* общее время выполнения

---

## 🧠 Особенности реализации

* Используется **upsert (ON CONFLICT)** для обновления данных
* Все записи пишутся в одной транзакции
* `commit` выполняется **один раз на кабинет**
* при ошибке выполняется `rollback`

---

## ⚠️ Важные замечания

### ❗ Не храните токены в БД

Используется безопасная схема:

```
token → SHA256 → cabinet_id
```

---

### ❗ Порядок токенов больше не важен

(в отличие от старой версии с WB_TOKENS)

---

### ❗ Если JSON сломан — токены не загрузятся

Проверьте валидность:

```bash
python -m json.tool
```

---

## 🚀 Деплой (Render)

* создать Web Service
* указать:

  ```
  uvicorn app.main:app --host 0.0.0.0 --port 10000
  ```
* добавить переменные окружения

---

## 📌 Планы развития

* bulk upsert (ускорение x10+)
* пагинация API
* фильтрация по seller_name
* UI панель

---

## 📄 Лицензия

MIT


