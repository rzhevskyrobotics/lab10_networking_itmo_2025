# Настройка Let's Encrypt с wildcard-сертификатами для ns-testing-rr.ru

---

## 1. Подготовка DNS (BIND)

1. Настроили собственный авторитетный DNS-сервер (**BIND**) для домена `ns-testing-rr.ru`.  
   В качестве NS выбраны:
   
   - `ns1.ns-testing-rr.ru` → `46.19.65.141`
   - `ns2.ns-testing-rr.ru` → `46.19.65.141`

2. В зоне добавить **A-записи**:
   
   ```dns
   ns1.ns-testing-rr.ru. IN A 46.19.65.141
   ns2.ns-testing-rr.ru. IN A 46.19.65.141
   ```

3. Проверить делегирование домена в панели регистратора (reg.ru) и дождаться применения NS.

---

## 2. Установка Certbot и плагина RFC2136

На сервере Ubuntu:

```bash
sudo apt update
sudo apt install certbot python3-certbot-dns-rfc2136
```

---

## 3. Конфигурация RFC2136

Создать файл `/etc/letsencrypt/rfc2136.ini`:

```ini
dns_rfc2136_server = 127.0.0.1
dns_rfc2136_port = 53
dns_rfc2136_name = certbot-key
dns_rfc2136_secret = SUPER_SECRET_KEY
dns_rfc2136_algorithm = HMAC-SHA256
```

### Создание TSIG-ключа

```bash
sudo tsig-keygen -a HMAC-SHA256 certbot-key > /etc/bind/certbot.key
```

---

## 4. Настройка BIND для работы с Certbot

В `named.conf.local` добавить:

### 🔹 Вариант 1. Упрощённый

```conf
include "/etc/bind/certbot.key";

zone "ns-testing-rr.ru" {
    type master;
    file "/etc/bind/db.ns-testing-rr.ru";
    update-policy {
        grant certbot-key zonesub ANY;
    };
};
```

Здесь ключу разрешено изменять **любые записи внутри зоны**. Работает надёжно, но небезопасно для продакшена.

---

### 🔹 Вариант 2. Безопасный

```conf
include "/etc/bind/certbot.key";

zone "ns-testing-rr.ru" {
    type master;
    file "/etc/bind/db.ns-testing-rr.ru";
    update-policy {
        grant certbot-key name _acme-challenge.ns-testing-rr.ru. txt;
    };
};
```

Здесь ключу разрешено обновлять **только TXT-записи** для `_acme-challenge.ns-testing-rr.ru`, которые нужны для валидации Let’s Encrypt.

---

## 5. Выпуск wildcard-сертификата

```bash
sudo certbot certonly   --dns-rfc2136   --dns-rfc2136-credentials /etc/letsencrypt/rfc2136.ini   -d "*.ns-testing-rr.ru" -d ns-testing-rr.ru
```

---

## 6. Проверка и обновление

Проверить срок действия:

```bash
sudo openssl x509 -in /etc/letsencrypt/live/ns-testing-rr.ru/fullchain.pem -noout -dates
```

Принудительная проверка обновления:

```bash
sudo certbot renew --dry-run
```

---

## 7. Интеграция с NGINX (пример)

```nginx
server {
    listen 443 ssl;
    server_name ns-testing-rr.ru *.ns-testing-rr.ru;

    ssl_certificate     /etc/letsencrypt/live/ns-testing-rr.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ns-testing-rr.ru/privkey.pem;

    root /var/www/html;
    index index.html;
}
```

---

PROFIT
