#!/usr/bin/env python3
"""
asn_lookup.py — модуль для определения принадлежности IP к автономной системе (AS).
Использует библиотеку ipwhois и RDAP-запросы.

Примеры запуска:
    python3 asn_lookup.py 8.8.8.8
    python3 asn_lookup.py 8.8.8.8 1.1.1.1 77.88.8.8
"""

import sys
import json
from ipwhois import IPWhois


def get_as_info(ip: str) -> dict:
    try:
        obj = IPWhois(ip)
        result = obj.lookup_rdap(depth=1)
        return {
            "ip": ip,
            "asn": result.get("asn"),
            "asn_description": result.get("asn_description"),
            "asn_country_code": result.get("asn_country_code"),
            "asn_date": result.get("asn_date"),
        }
    except Exception as e:
        return {"ip": ip, "error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 asn_lookup.py <IP1> <IP2> ...")
        sys.exit(1)

    ips = sys.argv[1:]
    results = [get_as_info(ip) for ip in ips]

    # JSON-вывод
    print(json.dumps(results, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
