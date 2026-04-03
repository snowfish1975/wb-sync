# WB Sync

Сервис синхронизации данных Wildberries. Раз в сутки запрашивает данные
через API Wildberries, сохраняет в PostgreSQL и отдаёт через REST API.

## Что умеет

- Поддержка нескольких кабинетов продавцов (несколько токенов)
- Ежедневная автоматическая синхронизация по расписанию
- Ручной запуск синхронизации через API
- Хранение истории синхронизаций в таблице логов
- REST API для получения сохранённых данных

Сейчас реализован один метод: **характеристики товаров** (cards/list).

## Технологии

- Python 3.11, FastAPI, SQLAlchemy
- PostgreSQL
- APScheduler (планировщик задач)
- Деплой: render.com

## Локальный запуск

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/ВАШ_ЛОГИН/wb-sync.git
cd wb-sync
```

### 2. Создайте виртуальное окружение
```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 3. Создайте файл .env

Скопируйте пример и заполните своими значениями:
```bash
cp .env.example .env
```

Содержимое .env:
```
DATABASE_URL=postgresql://user:password@localhost/wb_sync
WB_TOKENS=токен_кабинета_1,токен_кабинета_2
SYNC_HOUR=3
```

### 4. Запустите
```bash
uvicorn app.main:app --reload
```

Swagger UI будет доступен по адресу: http://localhost:8000/docs

## Переменные окружения

| Переменная   | Описание                                              | Пример                  |
|--------------|-------------------------------------------------------|-------------------------|
| DATABASE_URL | Строка подключения к PostgreSQL                       | postgresql://...        |
| WB_TOKENS    | Токены кабинетов через запятую                        | token1,token2,token3    |
| SYNC_HOUR    | Час запуска синхронизации (UTC)                       | 3                       |

## API

| Метод | Путь                  | Описание                                      |
|-------|-----------------------|-----------------------------------------------|
| GET   | /                     | Проверка работоспособности                    |
| GET   | /api/products         | Список сохранённых характеристик товаров      |
| GET   | /api/products?nm_id=X | Фильтр по артикулу WB                         |
| GET   | /api/products?cabinet=X | Фильтр по кабинету (первые 8 символов токена) |
| GET   | /api/logs             | История синхронизаций                         |
| POST  | /api/sync/trigger     | Запустить синхронизацию вручную               |
| GET   | /api/health           | Health check для мониторинга                  |

## Структура проекта
```
app/
├── main.py        # FastAPI приложение и планировщик
├── database.py    # подключение к PostgreSQL
├── models.py      # таблицы (SQLAlchemy)
├── schemas.py     # схемы ответов (Pydantic)
├── crud.py        # операции с БД
├── scheduler.py   # задачи синхронизации
└── wb_client.py   # клиент Wildberries API
```

## Деплой на Render

Подробная инструкция по деплою находится в [DEPLOY.md](DEPLOY.md).

Переменные окружения для Render:
- `DATABASE_URL` — Internal Database URL из настроек Render PostgreSQL
- `WB_TOKENS` — токены кабинетов через запятую
- `SYNC_HOUR` — час синхронизации (UTC, по умолчанию 3)

## Добавление нового метода WB API

1. Добавить модель таблицы в `models.py`
2. Добавить функции чтения/записи в `crud.py`
3. Добавить функцию запроса к WB в `wb_client.py`
4. Вызвать её в `scheduler.py` внутри `sync_one_cabinet()`
5. Добавить эндпоинт в `main.py`

## Известные ограничения

- Бесплатный план Render засыпает через 15 минут бездействия.
  Для надёжной работы планировщика нужен Starter план или внешний пинг
  (например, UptimeRobot на /api/health каждые 5 минут).
- Лимит хранения на бесплатной БД Render — 1 ГБ.