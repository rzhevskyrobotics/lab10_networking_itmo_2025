# Веб-приложение: мониторинг ASN и график RIPE NCC

## Описание

Веб-приложение по мониторингу использования DNS-резолверов и работе с автономными системами (ASN).

<u>Приложение</u>:

- Соотносит IP и DNS ASN

- определяет принадлежность IP к ASN через **Team Cymru** (whois) с резервом по **RADB** (origin из route/route6);

- принимает «пинг» с произвольным **токеном** и сохраняет IP→ASN в SQLite **без дублей по IP**;

- показывает статистику по ASN (ТОП-5, последние записи) и умеет её очищать;

- скачивает и кэширует на сервере файл статистики **RIPE NCC** (`delegated-ripencc-latest`), фронтенд **потоком** загружает его (прогресс-бар) и строит график выделения ASN российским LIR (год/накопительный итог);

- содержит простой **REST CRUD Items** для демонстрации работы фронта с серверной БД;

## Основная механика сопоставления IP и DNS

Для сопоставления HTTP- и DNS-запросов используется механизм анализа логов:

- В веб-приложении динамически генерируется **уникальный поддомен** (например, `abc123.ns-testing-rr.ru`).
- Браузер пользователя делает DNS-запрос за этим поддоменом → в логах BIND фиксируется **IP резолвера**.
- Далее браузер делает HTTP-запрос к серверу с этим же поддоменом → в логах HTTP фиксируется **IP пользователя**.
- По уникальному токену поддомена можно связать пользователя и резолвер, через который он работает.

---

## Стек

- **Frontend:** HTML, CSS, JS (+ Chart.js для графика)

- **Backend:** Python 3.12, FastAPI, Uvicorn

- **БД:** SQLite (SQLAlchemy + aiosqlite)

- **Веб-сервер:** NGINX (раздача статики + reverse proxy `/api`)

---

## Функциональность

- **IP → ASN** (Team Cymru) при `POST /api/ping`;

- **Статистика**: ТОП-5 ASN и последние записи; полная **очистка**;

- **RIPE NCC**: кэш файла на сервере, потоковая загрузка на фронт с прогрессом, **график** (годовой и накопительный) для `RU`;

- **REST CRUD Items**: список, добавление, удаление, inline-редактирование (PATCH/PUT), «список пуст» — аккуратный вывод;

- **Уведомления**: тосты вместо `alert`/консоли;

---

## Структура репозитория

```bash
webapp/
├─ frontend/
│  └─ static/
│     ├─ index.html         # UI: токен-пинг, статистика, RIPE-график, CRUD Items
│     ├─ css/               # стили (в т.ч. всплывающие сообщения)
│     └─ js/                # app.js (логика UI, прогресс загрузки RIPE, CRUD)
└─ backend/
   └─ app/
      ├─ main.py            # FastAPI маршруты
      ├─ models.py          # SQLAlchemy модели (TokenHit, Item и пр.)
      ├─ db.py              # init_db(), движок, индексы/дедуп
      ├─ asn_lookup.py      # Team Cymru + RADB (whois TCP/43)
      └─ settings.py        # общие константы
```

---

## Установка и запуск (сервер)

### Зависимости

```bash
sudo apt update
sudo apt install -y python3.12-venv python3-pip nginx sqlite3
```

### Развёртывание

```bash
# backend: venv + пакеты
cd webapp/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# если нет requirements.txt
pip install fastapi "uvicorn[standard]" sqlalchemy aiosqlite pydantic

# пробный запуск (создаст БД app.db и папку data/)
uvicorn app.main:app --host 127.0.0.1 --port 8095
# Ctrl+C для остановки
```

---

## NGINX конфиг

```bash
server {
    listen 80;
    server_name test.ns-testing-rr.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name test.ns-testing-rr.ru;

    # Сертификаты (Let's Encrypt)
    ssl_certificate     /etc/letsencrypt/live/ns-testing-rr.rufullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ns-testing-rr.ru/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Фронтенд (root указывает на папку static)
    root  /opt/webapp/webapp/frontend/static;
    index index.html;

    # Статика: css/js через alias
    location ^~ /css/ {
        alias /opt/webapp/webapp/frontend/static/css/;
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable";
        access_log off;
    }
    location ^~ /js/ {
        alias /opt/webapp/webapp/frontend/static/js/;
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable";
        access_log off;
    }

    # API → FastAPI (Uvicorn)
    location ^~ /api/ {
        proxy_pass http://127.0.0.1:8095;
        proxy_http_version 1.1;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location / {
        try_files $uri $uri/ @app;
    }

    location @app {
        proxy_pass http://127.0.0.1:8095;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## API (сводная таблица)

| Метод  | Путь                          | Назначение                                           | Вход                                  | Ключевые поля ответа                                         |
| ------ | ----------------------------- | ---------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------ |
| POST   | `/api/ping`                   | Пинг токеном, IP→ASN, запись **без дублей**          | `{ "token": "str" }`                  | `ip, asn, as_name, prefix, duplicate`                        |
| GET    | `/api/ping/stats`             | Статистика по пингам                                 | —                                     | `total_hits, unique_ips, top[]`                              |
| GET    | `/api/ping/last?limit=N`      | Последние N пингов                                   | —                                     | список `{when, token, ip, asn, as_name, prefix, user_agent}` |
| POST   | `/api/ping/clear`             | Очистка таблицы пингов                               | —                                     | `{deleted}`                                                  |
| GET    | `/api/items`                  | Список Items                                         | —                                     | `[]`                                                         |
| POST   | `/api/items`                  | Создать Item                                         | `{title, description?}`               | созданный объект                                             |
| PUT    | `/api/items/{id}`             | Полное обновление                                    | `{title, description?}`               | обновлённый объект                                           |
| PATCH  | `/api/items/{id}`             | Частичное обновление                                 | `{title? , description?}`             | обновлённый объект                                           |
| DELETE | `/api/items/{id}`             | Удалить                                              | —                                     | `{}` / 204                                                   |
| POST   | `/api/ripe/ensure?force=true` | false                                                | Скачать/обновить файл RIPE на сервере | —                                                            |
| GET    | `/api/ripe/file`              | Отдать локальный файл RIPE (для прогресса на фронте) | —                                     | **file** (с `Content-Length`)                                |

---

## Инструкция по использованию (UI)

1. **Ping токен**:
   
   Введите произвольный токен → **Отправить**.
   
   - первый пинг для IP: зелёный тост «Записано: …»;
   
   - повторный пинг того же IP: жёлтый тост «IP уже есть в базе…» (без дубля);
   
   - Кнопка **Показать статистику** — выведет суммарку, **ТОП-5 ASN** и **последние записи**;
   
   - Кнопка **Очистить статистику** — удалит все записи (подтверждение);

2. **RIPE NCC**:
   
   **Скачать и построить график** — сервер при необходимости докачает файл, браузер **потоком** загрузит его (progress `<progress>` по `Content-Length`) и построит график: «за год» и «накопительный итог» для `RU`;
   
   **Перескачать файл на сервере** — принудительное обновление кэша;

3. **Items (демо-CRUD)**:
   
   Добавление, удаление, **inline-редактирование** (PATCH/PUT). При пустом списке выводится «Список пуст…». Все операции сопровождаются тост-уведомлениями.

---

## Хранилище и файлы

- **SQLite**: `webapp/backend/app.db`  
  
  Основные таблицы:
  
  - `token_hits(ip, token, asn, as_name, prefix, user_agent, created_at)` — **уникальный индекс по `ip`**, чтобы запретить дубли;
  
  - `items(id, title, description, created_at)` — для демо-CRUD. (Схемы см. в `app/models.py`.);

- **Кэш RIPE**: `webapp/backend/data/delegated-ripencc-latest` Создаётся/обновляется через `POST /api/ripe/ensure` (автоматически при построении графика).
