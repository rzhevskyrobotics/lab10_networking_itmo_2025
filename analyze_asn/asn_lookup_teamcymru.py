#
# Этот скрипт работает через API Team Cymru и делает это ГОРАЗДО быстрее
#

#!/usr/bin/env python3
import re
import socket
from collections import Counter


LOG_RE = re.compile(r"client @\S+ (\d+\.\d+\.\d+\.\d+)#")


def parse_dns_logs(logfile):
    """Парсит IP-адреса резолверов из логов BIND"""
    ips = []
    with open(logfile, "r", encoding="utf-8") as f:
        for line in f:
            m = LOG_RE.search(line)
            if m:
                ips.append(m.group(1))
    return ips


def batch_ip_to_asn(ips):
    """
    Определяет ASN через Team Cymru WHOIS API.
    Возвращает словарь {ip: (asn, as_name)}.
    """
    if not ips:
        return {}

    results = {}
    query = "begin\nverbose\n" + "\n".join(ips) + "\nend\n"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("whois.cymru.com", 43))
        s.sendall(query.encode("utf-8"))
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    text = data.decode("utf-8")

    for line in text.splitlines():
        if line.startswith("AS"):
            continue  # заголовок
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 7:
            asn, ip, prefix, cc, registry, date, as_name = parts
            results[ip] = (asn, as_name)
    return results


def analyze(logfile, top_n=10):
    ips = parse_dns_logs(logfile)
    counter = Counter(ips)

    print(f"Всего запросов: {len(ips)}")
    print(f"Уникальных резолверов: {len(counter)}\n")

    # Определяем ASN только для уникальных IP
    asn_info = batch_ip_to_asn(list(counter.keys()))

    # Выводим топ-N резолверов
    print(f"Топ-{top_n} резолверов:")
    for ip, count in counter.most_common(top_n):
        asn, desc = asn_info.get(ip, ("?", "?"))
        print(f"{ip:15} → {count:5} запросов | AS{asn} {desc}")


if __name__ == "__main__":
    analyze("/var/log/named/query.log", top_n=15)
