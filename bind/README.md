# Настройка BIND для домена ns-testing-rr.ru

Этот документ описывает настройку авторитетного DNS-сервера BIND для домена `ns-testing-rr.ru`.

---

## 1. Установка BIND

На сервере Ubuntu:

```bash
sudo apt update
sudo apt install bind9 bind9utils bind9-doc
```

Проверка статуса:

```bash
systemctl status bind9
```

---

## 2. Настройка зоны

Файл `/etc/bind/named.conf.local`:

```conf
zone "ns-testing-rr.ru" {
    type master;
    file "/etc/bind/db.ns-testing-rr.ru";
};
```

Файл зоны `/etc/bind/db.ns-testing-rr.ru`:

```dns
$TTL    3600
@       IN      SOA     ns1.ns-testing-rr.ru. admin.ns-testing-rr.ru. (
                        2025093001 ; Serial
                        3600       ; Refresh
                        600        ; Retry
                        1209600    ; Expire
                        3600 )     ; Minimum TTL

        IN      NS      ns1.ns-testing-rr.ru.
        IN      NS      ns2.ns-testing-rr.ru.

ns1     IN      A       46.19.65.141
ns2     IN      A       46.19.65.141
@       IN      A       46.19.65.141
```

---

## 3. Настройка логирования запросов

В `named.conf.options` или `named.conf.local` добавить:

```conf
logging {
    channel query_log {
        file "/var/log/named/query.log" versions 3 size 50m;
        severity info;
        print-time yes;
    };
    category queries { query_log; };
};
```

/var/log/named/query.log - ОЧЕНЬ ВАЖНЫЙ ДЛЯ РАБОТЫ ЛОГ:)

Права на папку:

```bash
sudo mkdir -p /var/log/named
sudo chown bind:bind /var/log/named
```

---

## 4. Проверка конфигурации

Проверка конфигов:

```bash
sudo named-checkconf
```

Проверка зоны:

```bash
sudo named-checkzone ns-testing-rr.ru /etc/bind/db.ns-testing-rr.ru
```

Перезапуск:

```bash
sudo systemctl restart bind9
```

---

## 5. Тестирование

Запрос записи A:

```bash
dig @127.0.0.1 ns-testing-rr.ru A
```

Запрос NS:

```bash
dig @127.0.0.1 ns-testing-rr.ru NS
```

---

Это самая базовая настройка, потом были сделаны модификации для получения wildcard-серта на certbot и wildcard для поддержки динамических поддоменов.
